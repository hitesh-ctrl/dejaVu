from __future__ import annotations
import json
import stat
from datetime import datetime, timezone
from pathlib import Path
from .store import Rule, RuleStore


# Hook script uses Python for reliable JSON encoding.
# Verified against Claude Code hook docs: for PreToolUse events, context
# injection requires JSON output with "additionalContext" key (plain stdout
# only works for UserPromptSubmit/SessionStart events).
_HOOK_TEMPLATE = """\
#!/usr/bin/env python3
\"\"\"dejavu hook: {rule_id} - {signature}
Scope: {scope_description}

This script is a Claude Code PreToolUse hook. It injects a rule as context
before the matching tool call. It reads tool input JSON from stdin and
outputs additionalContext JSON to stdout.
\"\"\"
import json
import sys

sys.stdin.read()  # consume tool input JSON (required)
print(json.dumps({{"additionalContext": {rule_text_json}}}))
"""

_SETTINGS_TEMPLATE = """\
# Add this to ~/.claude/settings.json (all projects) or
# .claude/settings.json (this project only).
#
# Verified hook format: Claude Code docs, section "Hooks", PreToolUse event.
# The hook receives tool input JSON on stdin and may output a JSON object.
# "additionalContext" injects text as context for the assistant.

{{
  "hooks": {{
    "PreToolUse": [
      {{
        "matcher": {matcher_json},
        "hooks": [
          {{ "type": "command", "command": {script_path_json} }}
        ]
      }}
    ]
  }}
}}
"""

_CLAUDE_MD_TEMPLATE = """\
<!-- dejavu rule: {rule_id} | signature: {signature} -->

When calling {scope_description}: {rule_text}
"""


def emit_rule(rule: Rule, out_dir: Path, store: RuleStore) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scope = rule.scope
    tool = scope.get("tool") or "*"
    cmd_pat = scope.get("command_pattern")

    scope_desc = tool
    if cmd_pat:
        scope_desc += f" (command matches '{cmd_pat}')"

    # Hook script
    hook_path = out_dir / f"hook-{rule.rule_id}.py"
    hook_path.write_text(_HOOK_TEMPLATE.format(
        rule_id=rule.rule_id,
        signature=rule.signature,
        scope_description=scope_desc,
        rule_text_json=json.dumps(rule.rule_text),
    ))
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # Settings snippet
    settings_path = out_dir / f"settings-snippet-{rule.rule_id}.txt"
    settings_path.write_text(_SETTINGS_TEMPLATE.format(
        matcher_json=json.dumps(tool),
        script_path_json=json.dumps(str(hook_path.resolve())),
    ))

    # CLAUDE.md snippet
    claude_md_path = out_dir / f"claude-md-{rule.rule_id}.md"
    claude_md_path.write_text(_CLAUDE_MD_TEMPLATE.format(
        rule_id=rule.rule_id,
        signature=rule.signature,
        scope_description=scope_desc,
        rule_text=rule.rule_text,
    ))

    # Mark rule as activated
    rule.activated_at = datetime.now(timezone.utc).isoformat()
    store.add(rule)
    store.save()

    return {
        "hook_script": str(hook_path),
        "settings_snippet": str(settings_path),
        "claude_md_snippet": str(claude_md_path),
        "activated_at": rule.activated_at,
    }
