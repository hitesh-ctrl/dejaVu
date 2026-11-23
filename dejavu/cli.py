from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .parser import load_sessions_from
from .detector import build_sig_map, detect_mistakes
from .store import Rule, RuleStore
from .preview import preview_rule
from .emitter import emit_rule
from .measure import measure_rule
from .llm import draft_rule
from .report import generate_report
from .conflicts import check_conflicts
from .adapter import load_generic_sessions, is_generic_dir
from .drill import drill


def _load_store(rules_file: str) -> RuleStore:
    return RuleStore(path=rules_file)


def _load_sessions(path: str | None, fmt: str = "auto") -> list:
    if path is None:
        path = str(Path.home() / ".claude" / "projects")
    if fmt == "generic" or (fmt == "auto" and is_generic_dir(path)):
        return load_generic_sessions(path)
    return load_sessions_from(path)


def _get_rule(store: RuleStore, rule_id: str) -> Rule:
    rule = store.get(rule_id)
    if rule is None:
        print(f"Rule {rule_id} not found in {store.path}. Run 'analyze' first.")
        sys.exit(1)
    return rule


def cmd_analyze(args: argparse.Namespace) -> None:
    sessions = _load_sessions(args.sessions, getattr(args, "format", "auto"))
    n = len(sessions)
    if n == 0:
        print("No sessions found.")
        return

    source = args.sessions or str(Path.home() / ".claude" / "projects")
    print(f"Loaded {n} sessions from {source}\n")

    sig_map = build_sig_map(sessions)
    if not sig_map:
        print("No mistake signals detected.")
        return

    clusters = sorted(sig_map.items(), key=lambda x: -len(x[1]))
    top = clusters[: args.top]

    # Gather example errors per signature
    sig_errors: dict[str, list[str]] = {}
    for s in sessions:
        for signal in detect_mistakes(s):
            sig_errors.setdefault(signal.signature, []).append(signal.content_snippet)

    store = RuleStore(path=args.rules_file)
    store.sessions_dir = source
    store.session_count = n

    print("Top mistake clusters:\n")
    for i, (sig, session_ids) in enumerate(top):
        rule_id = f"r{i + 1:03d}"
        rule_text, scope = draft_rule(sig, sig_errors.get(sig, []), use_llm=not args.no_llm)

        rule = Rule(
            rule_id=rule_id,
            signature=sig,
            cluster_size=len(session_ids),
            example_sessions=sorted(session_ids)[:5],
            rule_text=rule_text,
            scope=scope,
            drafted_at=datetime.now(timezone.utc).isoformat(),
        )

        p = preview_rule(rule, sessions, sig_map)
        rule.preview_stats = p

        scope_str = ", ".join(
            f"{k}={v}" for k, v in scope.items() if v is not None
        )
        print(f"  {rule_id}  {sig}")
        print(f"       sessions: {len(session_ids)}")
        print(f"       scope: {scope_str}")
        fires = p["fires_in_sessions"]
        mistakes = p["mistake_in_sessions"]
        false_hits = p["false_hits"]
        print(f"       fires in {fires} sessions, mistake in {mistakes} ({false_hits} false hits)")
        print(f"       rule: {rule_text}")
        if getattr(args, "detail", False):
            print()
            print(drill(sig, sessions, session_ids))
        print()

        store.add(rule)

    store.save()
    print(f"Rules saved to {args.rules_file}")

    report_path = generate_report(sessions, top, store.all(), args.rules_file)
    print(f"Report saved to {report_path}")
    print(f"\nNext: python -m dejavu preview r001")


def cmd_preview(args: argparse.Namespace) -> None:
    store = _load_store(args.rules_file)
    rule = _get_rule(store, args.rule_id)

    scope_override = None
    if args.scope:
        try:
            scope_override = json.loads(args.scope)
        except json.JSONDecodeError as e:
            print(f"Invalid scope JSON: {e}")
            sys.exit(1)

    sessions = load_sessions_from(store.sessions_dir)
    sig_map = build_sig_map(sessions)

    p = preview_rule(rule, sessions, sig_map, scope_override=scope_override)
    scope_used = p["scope"]
    scope_str = ", ".join(f"{k}={v}" for k, v in scope_used.items() if v is not None)

    print(f"Rule {rule.rule_id}: {rule.signature}")
    print(f"Scope: {scope_str}\n")
    print(f"Fires in {p['fires_in_sessions']} of {p['total_sessions']} sessions.")
    print(f"Mistake present in {p['mistake_in_sessions']} of them "
          f"({p['false_hits']} false hits).")

    fires = p["fires_in_sessions"]
    mistakes = p["mistake_in_sessions"]
    if fires > 0:
        precision = mistakes / fires
        print()
        if precision < 0.5:
            print(f"  Precision: {precision:.0%}  (rule fires often with no mistake)")
            print("  Consider narrowing the scope to reduce false hits.")
        else:
            print(f"  Precision: {precision:.0%}  (acceptable)")
    print()
    print(f"Rule text: {rule.rule_text}")
    print()
    print(f"Next: python -m dejavu emit {rule.rule_id}")


def cmd_emit(args: argparse.Namespace) -> None:
    store = _load_store(args.rules_file)
    rule = _get_rule(store, args.rule_id)

    out_dir = Path(args.out_dir)
    result = emit_rule(rule, out_dir, store)

    print(f"Rule {rule.rule_id}: {rule.signature}\n")
    print(f"Hook script:      {result['hook_script']}")
    print(f"Settings snippet: {result['settings_snippet']}")
    print(f"CLAUDE.md snippet: {result['claude_md_snippet']}")
    print()
    print("Hook verified: fires on matching tool calls, injects additionalContext JSON.")
    print("Not verified: live session behavior -- run a test session to confirm.")
    print()
    print(f"Rule activated at {result['activated_at']}.")
    print(f"Next: python -m dejavu measure {rule.rule_id}")


def cmd_measure(args: argparse.Namespace) -> None:
    store = _load_store(args.rules_file)
    rule = _get_rule(store, args.rule_id)

    sessions_dir = args.sessions or store.sessions_dir
    sessions = _load_sessions(sessions_dir)

    result = measure_rule(rule, sessions)

    # Cache result into the rule so the report can include it
    rule.measure_result = result
    store.save()

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"Rule {rule.rule_id}: {rule.signature}")
    print(f"Activated: {rule.activated_at}\n")

    b = result["before"]
    a = result["after"]
    b_pct = f"{b['rate']:.1%}"
    a_pct = f"{a['rate']:.1%}"
    b_ci = f"{b['ci_95'][0]:.1%}-{b['ci_95'][1]:.1%}"
    a_ci = f"{a['ci_95'][0]:.1%}-{a['ci_95'][1]:.1%}"

    print(f"Before ({b['sessions']} sessions): "
          f"{b['mistakes']} of {b['sessions']} had mistake  ({b_pct}, 95% CI: {b_ci})")
    print(f"After  ({a['sessions']} sessions): "
          f"{a['mistakes']} of {a['sessions']} had mistake  ({a_pct}, 95% CI: {a_ci})")
    print()
    if result["small_sample_warning"]:
        print("Small sample warning: fewer than 20 sessions after activation.")
        print("Results are not reliable with this few sessions.")
        print()
    print(result["note"])


def cmd_conflicts(args: argparse.Namespace) -> None:
    store = _load_store(args.rules_file)
    rules = store.all()
    if len(rules) < 2:
        print("Need at least 2 rules to check for conflicts.")
        return

    conflicts = check_conflicts(rules, use_llm=not args.no_llm)
    real = [c for c in conflicts if c.severity != "none"]
    if not real:
        print(f"No conflicts found among {len(rules)} rules.")
        return

    print(f"Found {len(real)} potential conflict(s) among {len(rules)} rules:\n")
    for c in real:
        label = "CONTRADICTION" if c.severity == "contradiction" else "SCOPE OVERLAP"
        print(f"  [{label}] {c.rule_id_a} <-> {c.rule_id_b}")
        print(f"    {c.reasoning}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dejavu",
        description="Find repeated agent mistakes and draft scoped rules.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # analyze
    p_a = sub.add_parser("analyze", help="Detect clusters and draft rules")
    p_a.add_argument("--sessions", default=None, metavar="DIR",
                     help="Session directory (default: ~/.claude/projects/)")
    p_a.add_argument("--rules-file", default="rules.json", metavar="FILE")
    p_a.add_argument("--top", type=int, default=5, metavar="N",
                     help="Number of top clusters to show (default 5)")
    p_a.add_argument("--no-llm", action="store_true",
                     help="Skip LLM; use template rule text")
    p_a.add_argument("--format", choices=["auto", "claude", "generic"], default="auto",
                     metavar="FMT", help="Input format: auto (default), claude, generic")
    p_a.add_argument("--detail", action="store_true",
                     help="Show per-cluster breakdown of commands and error samples")

    # preview
    p_p = sub.add_parser("preview", help="Show scope firing stats for a rule")
    p_p.add_argument("rule_id")
    p_p.add_argument("--rules-file", default="rules.json", metavar="FILE")
    p_p.add_argument("--scope", default=None, metavar="JSON",
                     help="Override scope, e.g. '{\"tool\":\"Edit\",\"command_pattern\":\"src/\"}'")

    # emit
    p_e = sub.add_parser("emit", help="Generate hook script and CLAUDE.md snippet")
    p_e.add_argument("rule_id")
    p_e.add_argument("--rules-file", default="rules.json", metavar="FILE")
    p_e.add_argument("--out-dir", default=".dejavu", metavar="DIR")

    # measure
    p_m = sub.add_parser("measure", help="Compare mistake rate before/after activation")
    p_m.add_argument("rule_id")
    p_m.add_argument("--rules-file", default="rules.json", metavar="FILE")
    p_m.add_argument("--sessions", default=None, metavar="DIR")

    # conflicts
    p_c = sub.add_parser("conflicts", help="Check rules for scope overlap or contradictions")
    p_c.add_argument("--rules-file", default="rules.json", metavar="FILE")
    p_c.add_argument("--no-llm", action="store_true",
                     help="Skip LLM contradiction check; report overlaps only")

    args = parser.parse_args()

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "preview":
        cmd_preview(args)
    elif args.command == "emit":
        cmd_emit(args)
    elif args.command == "measure":
        cmd_measure(args)
    elif args.command == "conflicts":
        cmd_conflicts(args)
    else:
        parser.print_help()
        sys.exit(1)
