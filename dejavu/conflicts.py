"""
Rule conflict checker.

Flags pairs of rules whose scopes overlap and whose text may contradict.
Scope overlap is checked deterministically. Contradiction judgment uses the
LLM (falls back to a manual-review notice when --no-llm is set).
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field
from .store import Rule
from .redact import redact


@dataclass
class Conflict:
    rule_id_a: str
    rule_id_b: str
    scope_overlap: bool
    contradiction: bool | None   # None when LLM was not used
    reasoning: str
    severity: str                # "contradiction" | "overlap" | "none"


def _scopes_overlap(a: dict, b: dict) -> bool:
    tool_a = a.get("tool")
    tool_b = b.get("tool")
    # Both specify a tool and they differ -> cannot both fire on the same event
    if tool_a and tool_b and tool_a != tool_b:
        return False
    # Both have command_pattern: a true regex intersection check is undecidable,
    # so we conservatively say they overlap and let the user decide.
    return True


def _llm_contradiction(rule_a: Rule, rule_b: Rule) -> tuple[bool | None, str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None, "No ANTHROPIC_API_KEY; scope overlap detected, check manually."
    try:
        import anthropic  # type: ignore

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "Two rules are both scoped to fire before the same type of tool call.\n\n"
            f"Rule {rule_a.rule_id}: {redact(rule_a.rule_text)}\n"
            f"Rule {rule_b.rule_id}: {redact(rule_b.rule_text)}\n\n"
            "Do these rules contradict each other? A contradiction means that "
            "following one rule would conflict with following the other in the "
            "same situation.\n\n"
            "Respond with JSON only:\n"
            "{\"contradiction\": true|false, \"reasoning\": \"one sentence\"}"
        )
        resp = client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return bool(data["contradiction"]), str(data["reasoning"])
    except Exception as exc:
        return None, f"LLM check failed: {exc}"
    return None, "Could not parse LLM response."


def check_conflicts(
    rules: list[Rule],
    use_llm: bool = True,
) -> list[Conflict]:
    results: list[Conflict] = []
    for i, a in enumerate(rules):
        for b in rules[i + 1:]:
            overlap = _scopes_overlap(a.scope, b.scope)
            if not overlap:
                results.append(Conflict(
                    rule_id_a=a.rule_id,
                    rule_id_b=b.rule_id,
                    scope_overlap=False,
                    contradiction=False,
                    reasoning="Scopes do not overlap; these rules cannot both fire.",
                    severity="none",
                ))
                continue

            if use_llm:
                contradiction, reasoning = _llm_contradiction(a, b)
            else:
                contradiction = None
                reasoning = "LLM disabled. Scope overlap detected; check rule texts manually."

            if contradiction is True:
                severity = "contradiction"
            elif overlap:
                severity = "overlap"
            else:
                severity = "none"

            results.append(Conflict(
                rule_id_a=a.rule_id,
                rule_id_b=b.rule_id,
                scope_overlap=overlap,
                contradiction=contradiction,
                reasoning=reasoning,
                severity=severity,
            ))

    return results
