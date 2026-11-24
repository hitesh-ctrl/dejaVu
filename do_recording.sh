#!/usr/bin/env bash
# Orchestrates: open Terminal -> launch demo -> record 65s with auto-stop -> annotate

RAW="/Users/hiteshvenu/dejaVu/dejavu-screenrecord-raw.mp4"
FINAL="/Users/hiteshvenu/dejaVu/dejavu-demo-final.mp4"

rm -f "$RAW" "$FINAL"

echo "1/3  Opening Terminal and launching demo..."
osascript -e 'tell application "Terminal" to activate'
sleep 0.4
osascript -e 'tell application "Terminal" to do script "clear"'
sleep 0.4
osascript -e 'tell application "Terminal" to set bounds of front window to {0, 23, 1440, 900}'
sleep 1.5

# Launch demo (non-blocking -- Terminal runs it independently)
osascript -e 'tell application "Terminal" to do script "cd ~/dejaVu && bash record_demo.sh" in front window'
sleep 1   # let demo appear on screen before recording starts

echo "2/3  Recording for 100s (auto-stops)..."
ffmpeg -f avfoundation \
  -framerate 30 \
  -i "2" \
  -t 100 \
  -c:v libx264 \
  -crf 15 \
  -preset ultrafast \
  -movflags faststart \
  -pix_fmt yuv420p \
  "$RAW"

ls -lh "$RAW"
echo "3/3  Annotating..."
bash /Users/hiteshvenu/dejaVu/annotate_video.sh

ls -lh "$FINAL"
echo "Done: $FINAL"
