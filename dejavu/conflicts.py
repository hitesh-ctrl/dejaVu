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


def _contradiction_prompt(rule_a: Rule, rule_b: Rule) -> str:
    return (
        "Two rules are both scoped to fire before the same type of tool call.\n\n"
        f"Rule {rule_a.rule_id}: {redact(rule_a.rule_text)}\n"
        f"Rule {rule_b.rule_id}: {redact(rule_b.rule_text)}\n\n"
        "Do these rules contradict each other? A contradiction means that "
        "following one rule would conflict with following the other in the "
        "same situation.\n\n"
        "Respond with JSON only:\n"
        "{\"contradiction\": true|false, \"reasoning\": \"one sentence\"}"
    )


def _parse_contradiction(raw: str) -> tuple[bool | None, str]:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            return bool(data["contradiction"]), str(data["reasoning"])
        except (json.JSONDecodeError, KeyError):
            pass
    return None, "Could not parse LLM response."


def _llm_contradiction(rule_a: Rule, rule_b: Rule) -> tuple[bool | None, str]:
    import urllib.request as _urllib
    prompt = _contradiction_prompt(rule_a, rule_b)

    groq_key = os.environ.get("GROQ_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not groq_key and not anthropic_key:
        return None, "No GROQ_API_KEY or ANTHROPIC_API_KEY; scope overlap detected, check manually."

    if groq_key:
        try:
            payload = json.dumps({
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 128,
            }).encode()
            req = _urllib.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=payload,
                headers={"Authorization": f"Bearer {groq_key}",
                         "Content-Type": "application/json"},
            )
            with _urllib.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            raw = data["choices"][0]["message"]["content"].strip()
            result, reasoning = _parse_contradiction(raw)
            if result is not None:
                return result, reasoning
        except Exception as exc:
            pass  # fall through to Anthropic

    if anthropic_key:
        try:
            import anthropic  # type: ignore
            client = anthropic.Anthropic(api_key=anthropic_key)
            resp = client.messages.create(
                model="claude-haiku-5-5",
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )
            return _parse_contradiction(resp.content[0].text.strip())
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
