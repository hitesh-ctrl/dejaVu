"""
Detailed breakdown of what's behind a mistake cluster.

For Bash errors: buckets commands by first token, shows top examples.
For user corrections: shows the correction messages.
For other tool errors: shows error content samples.
"""
from __future__ import annotations
import re
import collections
from .parser import Session
from .redact import redact

_ANSI = re.compile(r'\x1b\[[0-9;]*m')


def _strip(s: str) -> str:
    return _ANSI.sub('', s).replace('\n', ' ').strip()


def _first_token(cmd: str) -> str:
    cmd = cmd.strip()
    if not cmd:
        return "(empty)"
    tok = cmd.split()[0].split("/")[-1]
    return tok


def _is_exit_code_error(content: str) -> bool:
    low = content.lower()
    return "exit code" in low or "exit_code" in low


def drill_bash_errors(
    signature: str,
    sessions: list[Session],
    sig_session_ids: set[str],
    top_n: int = 8,
    examples_per_bucket: int = 2,
) -> str:
    """Return a formatted breakdown of Bash error commands for a signature."""
    buckets: collections.Counter = collections.Counter()
    examples: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    total_hits = 0

    for s in sessions:
        if s.session_id not in sig_session_ids:
            continue
        pending: dict[str, str] = {}  # tool_use_id -> command
        tool_names: dict[str, str] = {}  # tool_use_id -> tool name
        for ev in s.events:
            if ev.kind == "tool_use":
                uid = ev.tool_use_id or ""
                tool_names[uid] = ev.tool_name or ""
                if ev.tool_name == "Bash":
                    pending[uid] = ev.tool_input.get("command", "")
            elif ev.kind == "tool_result" and ev.is_error:
                content = ev.content or ""
                uid = ev.tool_use_id or ""
                cmd = pending.get(uid)
                # Non-Bash errors (e.g. Edit/Write without prior read) get labeled by tool
                if cmd is None:
                    tname = tool_names.get(uid) or ev.tool_name or "other"
                    tok = f"({tname})"
                else:
                    tok = _first_token(cmd)
                buckets[tok] += 1
                total_hits += 1
                if len(examples[tok]) < examples_per_bucket:
                    examples[tok].append((
                        redact(cmd[:120]) if cmd else "",
                        _strip(redact(content))[:160],
                    ))

    if not buckets:
        return "  (no Bash error details found)\n"

    lines = [f"  {total_hits} error hits across {len(sig_session_ids)} sessions\n"]
    lines.append("  Commands by first token:")
    for tok, count in buckets.most_common(top_n):
        lines.append(f"    {count:3d}  {tok}")
    lines.append("")
    lines.append("  Examples:")
    for tok, _ in buckets.most_common(top_n):
        lines.append(f"    -- {tok} --")
        for cmd, err in examples[tok]:
            lines.append(f"      cmd: {cmd}")
            lines.append(f"      err: {err}")
        lines.append("")
    return "\n".join(lines)


def drill_corrections(
    signature: str,
    sessions: list[Session],
    sig_session_ids: set[str],
    examples_n: int = 5,
) -> str:
    """Return sample user correction messages for a user_correction cluster."""
    snippets: list[str] = []
    _CORRECTION_RE = re.compile(
        r'\b(no[,\.!]|i said|that\'s wrong|that is wrong|not what i|'
        r'didn\'t ask|did not ask|you\'re wrong|stop doing|don\'t do that|'
        r'wrong approach|that\'s not|that is not what)\b',
        re.IGNORECASE,
    )
    for s in sessions:
        if s.session_id not in sig_session_ids:
            continue
        for ev in s.events:
            if ev.kind == "user_msg" and len(snippets) < examples_n:
                content = (ev.content or "").strip()
                # Skip messages that are clearly terminal pastes or task notifications
                if content.startswith("<") or content.startswith("%") or len(content) > 400:
                    continue
                if _CORRECTION_RE.search(content):
                    snippets.append(redact(content[:160]))

    if not snippets:
        return "  (no correction message samples found)\n"

    lines = [f"  {len(sig_session_ids)} sessions with user corrections\n"]
    lines.append("  Sample correction messages:")
    for s in snippets:
        lines.append(f"    - {s}")
    lines.append("")
    return "\n".join(lines)


def drill_tool_errors(
    signature: str,
    sessions: list[Session],
    sig_session_ids: set[str],
    examples_n: int = 5,
) -> str:
    """Return sample error content for a generic tool error cluster."""
    tool = signature.split(":")[0] if ":" in signature else signature
    snippets: list[str] = []
    for s in sessions:
        if s.session_id not in sig_session_ids:
            continue
        for ev in s.events:
            if ev.kind == "tool_result" and ev.is_error and len(snippets) < examples_n:
                if ev.tool_name == tool or not ev.tool_name:
                    snippets.append(_strip(redact(ev.content or ""))[:160])

    if not snippets:
        return "  (no error samples found)\n"

    lines = [f"  {len(sig_session_ids)} sessions with {tool} errors\n"]
    lines.append("  Sample errors:")
    for s in snippets:
        lines.append(f"    - {s}")
    lines.append("")
    return "\n".join(lines)


def drill(
    signature: str,
    sessions: list[Session],
    sig_session_ids: set[str],
) -> str:
    """Dispatch to the right drill function based on signature shape."""
    if signature.startswith("user_correction"):
        return drill_corrections(signature, sessions, sig_session_ids)
    tool = signature.split(":")[0] if ":" in signature else signature
    if tool == "Bash":
        return drill_bash_errors(signature, sessions, sig_session_ids)
    return drill_tool_errors(signature, sessions, sig_session_ids)
