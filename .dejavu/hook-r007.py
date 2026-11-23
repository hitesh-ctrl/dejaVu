#!/usr/bin/env python3
"""dejavu hook: r007 - Bash:sed:macos_flag
Scope: Bash (command matches 'sed -i ')

This script is a Claude Code PreToolUse hook. It injects a rule as context
before the matching tool call. It reads tool input JSON from stdin and
outputs additionalContext JSON to stdout.
"""
import json
import sys

sys.stdin.read()  # consume tool input JSON (required)
print(json.dumps({"additionalContext": "On macOS, sed -i requires an empty string argument: use `sed -i '' 's/find/replace/' file`, not `sed -i 's/find/replace/' file`. Omitting the empty string causes exit code 1."}))
