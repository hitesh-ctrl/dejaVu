#!/usr/bin/env bash
# Post-process raw recording: crop menu bar, overlay subtitles.
# Input:  dejavu-screenrecord-raw.mp4
# Output: dejavu-demo-final.mp4
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT="$SCRIPT_DIR/dejavu-screenrecord-raw.mp4"
OUTPUT="$SCRIPT_DIR/dejavu-demo-final-50s.mp4"
TMP="$SCRIPT_DIR/.annotate-tmp"

if [[ ! -f "$INPUT" ]]; then
  echo "ERROR: $INPUT not found. Run do_recording.sh first."
  exit 1
fi

mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

# Total duration and per-segment durations (must sum to DURATION).
# Segments map 1-to-1 to generate_panels.py VOICEOVER entries.
#   0 intro         4s
#   1 gen_samples   5s
#   2 analyze       5s
#   3 results       5s
#   4 open browser  3s
#   5 report top    5s
#   6 scroll        13s
#   7 preview       5s
#   8 emit          5s
#   9 hook code     4s
#  10 measure       6s
#  11 tagline       3s
DURATION=63
declare -a DURS=(4 5 5 5 3 5 13 5 5 4 6 3)

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

# ── 3. Composite: crop menu bar (top 50px), overlay subtitles ────────────────
echo "3/3  Compositing..."

ffmpeg -y \
  -i "$INPUT" \
  -i "$TMP/overlay.mkv" \
  -filter_complex "
    [0:v]trim=start=2:duration=${DURATION},setpts=PTS-STARTPTS,
         crop=2560:1614:0:50[main];
    [main][1:v]overlay=x=0:y=0[out]
  " \
  -map "[out]" \
  -c:v libx264 -crf 8 -preset slow -pix_fmt yuv420p -movflags faststart \
  "$OUTPUT"

echo "Done."
ls -lh "$OUTPUT"
echo "Output: $OUTPUT"
