#!/usr/bin/env python3
"""dejavu hook: r001 - Bash:error:exit_code_1
Scope: Bash (command matches 'sed|git-filter|build|npm|yarn|pnpm|vite')

This script is a Claude Code PreToolUse hook. It injects a rule as context
before the matching tool call. It reads tool input JSON from stdin and
outputs additionalContext JSON to stdout.
"""
import json
import sys

sys.stdin.read()  # consume tool input JSON (required)
print(json.dumps({"additionalContext": "Verify that special characters like pipes, dashes, and email symbols are properly escaped or the command is single-quoted before running Bash commands that use sed, git history rewriting, or external build tools."}))
