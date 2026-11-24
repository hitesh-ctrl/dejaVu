#!/usr/bin/env bash
# Post-process: trim to 33s, overlay subtitles (no audio, no fades).
# Input:  dejavu-screenrecord-raw.mp4
# Output: dejavu-demo-final.mp4
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT="$SCRIPT_DIR/dejavu-screenrecord-raw.mp4"
OUTPUT="$SCRIPT_DIR/dejavu-demo-final.mp4"
TMP="$SCRIPT_DIR/.annotate-tmp"

if [[ ! -f "$INPUT" ]]; then
  echo "ERROR: $INPUT not found. Run do_recording.sh first."
  exit 1
fi

mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

DURATION=61

# Segment durations (must sum to $DURATION):
#   0 intro  1 gen  2 analyze  3 results  4 open-browser(fullscreen)
#   5 report-top  6 scroll  7 terminal-back+preview  8 emit  9 hook  10 measure  11 tagline
declare -a DURS=(4 4 6 5 4 5 12 5 5 4 4 3)

# ── 1. Generate subtitle overlay PNGs ────────────────────────────────────────
echo "1/3  Generating subtitle overlays..."
python3 "$SCRIPT_DIR/generate_panels.py" "$TMP"

# ── 2. Build subtitle overlay segments (yuva420p for alpha) ──────────────────
echo "2/3  Building overlay segments..."
for i in 0 1 2 3 4 5 6 7 8 9 10 11; do
  ffmpeg -y -loglevel error \
    -loop 1 -framerate 2 -i "$TMP/dv_panel_${i}.png" \
    -t "${DURS[$i]}" \
    -c:v ffv1 -pix_fmt yuva420p \
    "$TMP/seg_${i}.mkv"
done

{
  for i in 0 1 2 3 4 5 6 7 8 9 10 11; do
    echo "file '${TMP}/seg_${i}.mkv'"
  done
} > "$TMP/concat.txt"

ffmpeg -y -loglevel error \
  -f concat -safe 0 -i "$TMP/concat.txt" \
  -c:v ffv1 -pix_fmt yuva420p \
  "$TMP/overlay.mkv"

# ── 3. Composite video + subtitle overlay ────────────────────────────────────
echo "3/3  Compositing..."

ffmpeg -y \
  -i "$INPUT" \
  -i "$TMP/overlay.mkv" \
  -filter_complex "
    [0:v]trim=start=2:duration=${DURATION},setpts=PTS-STARTPTS[main];
    [main][1:v]overlay=x=0:y=0[out]
  " \
  -map "[out]" \
  -c:v libx264 -crf 8 -preset slow -pix_fmt yuv420p -movflags faststart \
  "$OUTPUT"

echo "Done."
ls -lh "$OUTPUT"
echo "Output: $OUTPUT"
