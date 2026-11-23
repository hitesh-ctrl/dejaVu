from __future__ import annotations
import os
import re
import json
from .redact import redact


def _template(signature: str) -> tuple[str, dict]:
    parts = signature.split(":")
    tool = parts[0] if parts else "unknown"

    if signature == "Edit:file_not_read":
        text = (
            "Before calling Edit on a file, verify you have called Read on "
            "that file in this session."
        )
        scope: dict = {"tool": "Edit", "command_pattern": None}

    elif len(parts) >= 2 and parts[1] == "enoent":
        item = parts[2] if len(parts) > 2 else "the required path"
        text = (
            f"Verify {item} exists in the current working directory before "
            "running this command."
        )
        scope = {"tool": tool, "command_pattern": None}

    elif signature == "user_correction":
        text = (
            "Re-read the user's original request before proceeding. "
            "Confirm your plan matches what was asked."
        )
        # User corrections are not hookable via PreToolUse
        scope = {"tool": None, "trigger": "user_msg_correction"}

    elif "permission_denied" in signature:
        text = f"Check permissions before calling {tool}."
        scope = {"tool": tool, "command_pattern": None}

    else:
        text = f"Double-check the input to {tool} before proceeding."
        scope = {"tool": tool, "command_pattern": None}

    return text, scope


def draft_rule(
    signature: str,
    example_errors: list[str],
    use_llm: bool = True,
) -> tuple[str, dict]:
    if not use_llm:
        return _template(signature)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _template(signature)

    try:
        import anthropic  # type: ignore

        client = anthropic.Anthropic(api_key=api_key)
        examples = [redact(e) for e in example_errors[:3]]
        prompt = (
            "You are helping write a scoped rule for a Claude Code agent.\n\n"
            f"Signature of the repeated mistake: {signature}\n"
            "Example error messages (redacted):\n"
            + "\n".join(f"- {e}" for e in examples)
            + "\n\nWrite:\n"
            "1. A short rule (one sentence, plain language, no em dashes) telling "
            "the agent what to check BEFORE the failing step.\n"
            "2. A scope: a JSON object with \"tool\" (tool name string or null) and "
            "\"command_pattern\" (regex string or null).\n\n"
            "Respond with JSON only:\n"
            "{\"rule_text\": \"...\", \"scope\": {\"tool\": \"...\", \"command_pattern\": null}}"
        )
        resp = client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return data["rule_text"], data["scope"]
    except Exception:
        pass

    return _template(signature)
