#!/usr/bin/env bash
# Recording-friendly demo script - slowed for readability, countdown at end
set -e
cd "$(dirname "$0")"

DEMO_SESSIONS="/tmp/dejavu-demo-sessions"
DEMO_RULES="/tmp/dejavu-demo-rules.json"

_type() {
  echo -e "\033[1;32m\$\033[0m \033[1m$*\033[0m"
  sleep 0.6
}

_pause() { sleep "${1:-1}"; }

clear
echo ""
echo -e "  \033[1;37mdejavu\033[0m  --  find the mistakes your AI agent keeps repeating"
echo ""
_pause 3

# ── Step 1: generate synthetic sessions ──────────────────────────────────────
_type "python3 gen_samples.py $DEMO_SESSIONS/"
python3 gen_samples.py "$DEMO_SESSIONS/" 2>&1 | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  Generated {d[\"total_sessions\"]} synthetic sessions')"
_pause 2.5

echo ""

# ── Step 2: analyze ──────────────────────────────────────────────────────────
_type "python3 -m dejavu analyze --sessions $DEMO_SESSIONS/ --rules-file $DEMO_RULES --no-llm"
python3 -m dejavu analyze \
  --sessions "$DEMO_SESSIONS/" \
  --rules-file "$DEMO_RULES" \
  --no-llm 2>&1
_pause 4

echo ""

# ── Step 3: preview r001 ─────────────────────────────────────────────────────
_type "python3 -m dejavu preview r001 --rules-file $DEMO_RULES"
python3 -m dejavu preview r001 --rules-file "$DEMO_RULES" 2>&1
_pause 3

echo ""

# ── Step 4: emit hook ────────────────────────────────────────────────────────
_type "python3 -m dejavu emit r001 --rules-file $DEMO_RULES --out-dir /tmp/dejavu-demo-hooks"
python3 -m dejavu emit r001 \
  --rules-file "$DEMO_RULES" \
  --out-dir /tmp/dejavu-demo-hooks 2>&1
_pause 3

echo ""

# ── Step 5: show hook output ──────────────────────────────────────────────────
_type "cat /tmp/dejavu-demo-hooks/hook-r001.py  # fires before every Edit call"
echo ""
head -20 /tmp/dejavu-demo-hooks/hook-r001.py
echo "..."
_pause 3

echo ""
echo -e "  \033[1;32m✓\033[0m  Rule active. Run \033[1mpython3 -m dejavu measure r001\033[0m after your next sessions."
echo ""
_pause 2

# Countdown so the recording ends cleanly
echo -e "  \033[2m-- recording ends in --\033[0m"
for i in 5 4 3 2 1; do
  printf "\r  \033[2m%d...\033[0m  " "$i"
  sleep 1
done
printf "\r  \033[1;32mdone\033[0m              \n"
echo ""
