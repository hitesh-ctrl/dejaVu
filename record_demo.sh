#!/usr/bin/env bash
# Recording-friendly demo script.
# Segment boundaries are marked with their expected duration so annotate_video.sh
# DURS can stay in sync with actual on-screen timing.
set -e
cd "$(dirname "$0")"

DEMO_SESSIONS="/tmp/dejavu-demo-sessions"
DEMO_RULES="/tmp/dejavu-demo-rules.json"
DEMO_HOOKS="/tmp/dejavu-demo-hooks"

_type() {
  echo -e "\033[1;32m\$\033[0m \033[1m$*\033[0m"
  sleep 0.5
}

_pause() { sleep "${1:-1}"; }

# ── SEG 0  4s ──────────────────────────────────────────────────────────────
clear
echo ""
echo -e "  \033[1;37mdejavu\033[0m  --  find the mistakes your AI agent keeps repeating"
echo ""
_pause 4

# ── SEG 1  5s ──────────────────────────────────────────────────────────────
_type "python3 gen_samples.py $DEMO_SESSIONS/"
python3 gen_samples.py "$DEMO_SESSIONS/" 2>&1 \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  Generated {d[\"total_sessions\"]} synthetic sessions')"
_pause 4

echo ""

# ── SEG 2  5s ──────────────────────────────────────────────────────────────
_type "python3 -m dejavu analyze --sessions $DEMO_SESSIONS/ --rules-file $DEMO_RULES --no-llm"
python3 -m dejavu analyze \
  --sessions "$DEMO_SESSIONS/" \
  --rules-file "$DEMO_RULES" \
  --no-llm 2>&1
_pause 1

# ── SEG 3  5s ──────────────────────────────────────────────────────────────
# results are on screen; let viewer read them
_pause 5

echo ""

# ── SEG 4  3s ──────────────────────────────────────────────────────────────
_type "open /tmp/report.html  # interactive breakdown in the browser"
open -a Safari /tmp/report.html
_pause 2

# ── SEG 5  5s ──────────────────────────────────────────────────────────────
# Safari report top visible in full screen
osascript -e 'tell application "Safari" to set zoomed of front window to true'
_pause 1
_pause 4

# ── SEG 6  13s ─────────────────────────────────────────────────────────────
# scroll slowly through the report
osascript -e 'tell application "Safari" to do JavaScript "window.scrollBy({top: 400, behavior: \"smooth\"})" in front document'
_pause 3
osascript -e 'tell application "Safari" to do JavaScript "window.scrollBy({top: 400, behavior: \"smooth\"})" in front document'
_pause 3
osascript -e 'tell application "Safari" to do JavaScript "window.scrollBy({top: 400, behavior: \"smooth\"})" in front document'
_pause 3
osascript -e 'tell application "Safari" to do JavaScript "window.scrollBy({top: 400, behavior: \"smooth\"})" in front document'
_pause 3
# unzoom Safari, switch back to Terminal
osascript -e 'tell application "Safari" to set zoomed of front window to false'
_pause 1

# ── SEG 7  5s ──────────────────────────────────────────────────────────────
osascript -e 'tell application "Terminal" to activate'
_pause 1
_type "python3 -m dejavu preview r001 --rules-file $DEMO_RULES"
python3 -m dejavu preview r001 --rules-file "$DEMO_RULES" 2>&1
_pause 2

echo ""

# ── SEG 8  5s ──────────────────────────────────────────────────────────────
_type "python3 -m dejavu emit r001 --rules-file $DEMO_RULES --out-dir $DEMO_HOOKS"
python3 -m dejavu emit r001 \
  --rules-file "$DEMO_RULES" \
  --out-dir "$DEMO_HOOKS" 2>&1
_pause 3

echo ""

# ── SEG 9  4s ──────────────────────────────────────────────────────────────
_type "cat $DEMO_HOOKS/hook-r001.py  # fires before every Edit call"
echo ""
head -20 "$DEMO_HOOKS/hook-r001.py"
echo "..."
_pause 3

echo ""

# ── SEG 10  6s ─────────────────────────────────────────────────────────────
_type "python3 -m dejavu measure r001 --sessions $DEMO_SESSIONS/ --rules-file $DEMO_RULES"
python3 -m dejavu measure r001 \
  --sessions "$DEMO_SESSIONS/" \
  --rules-file "$DEMO_RULES" 2>&1
_pause 4

# ── SEG 11  3s ─────────────────────────────────────────────────────────────
echo ""
echo -e "  \033[1;32m✓\033[0m  Find it. Fix it. Measure it."
echo ""
_pause 3
