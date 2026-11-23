#!/usr/bin/env python3
"""dejavu hook: r006 - Edit:file_not_read
Scope: Edit

This script is a Claude Code PreToolUse hook. It injects a rule as context
before the matching tool call. It reads tool input JSON from stdin and
outputs additionalContext JSON to stdout.
"""
import json
import sys

sys.stdin.read()  # consume tool input JSON (required)
print(json.dumps({"additionalContext": "Before calling Edit on a file, you must have called Read on that exact file path in this session. If you have not read it, call Read first."}))
