#!/bin/bash
# dejavu demo
# Runs the full loop on the synthetic samples. No LLM key required.
# Takes about 5 seconds.
set -euo pipefail

RULES=demo-rules.json
HOOKS_DIR=demo-hooks

echo "=== dejavu demo ==="
echo ""

# 1. Generate synthetic sessions
echo "Step 1: Generating 47 synthetic sessions in samples/"
python3 gen_samples.py samples/
echo ""

# 2. Analyze
echo "Step 2: Analyzing..."
python3 -m dejavu analyze \
  --sessions samples/ \
  --rules-file "$RULES" \
  --no-llm
echo ""

# 3. Preview the top rule -- too broad
echo "Step 3: Preview r001 (broad scope: fires in 30 sessions, only 11 had the mistake)"
python3 -m dejavu preview r001 --rules-file "$RULES"
echo ""

# 4. Preview with a narrowed scope (src/ files only)
echo "Step 4: Narrowed scope (file_pattern=src/) -- fewer fires, some mistakes missed"
python3 -m dejavu preview r001 \
  --rules-file "$RULES" \
  --scope '{"tool": "Edit", "file_pattern": "src/"}'
echo ""

# 5. Emit the hook
echo "Step 5: Emit hook for r001"
python3 -m dejavu emit r001 \
  --rules-file "$RULES" \
  --out-dir "$HOOKS_DIR"
echo ""

echo "=== done ==="
echo ""
echo "Hook script output (what Claude Code injects before each Edit call):"
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/app.ts"}}' \
  | python3 "$HOOKS_DIR/hook-r001.py"
echo ""
echo "Open report.html (created in the working directory) to see the full report."
echo "Settings snippet is at $HOOKS_DIR/settings-snippet-r001.txt"
