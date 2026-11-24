#!/usr/bin/env bash
# Orchestrates: set dark wallpaper → open Terminal → launch demo → record → annotate → restore wallpaper

RAW="/Users/hiteshvenu/dejaVu/dejavu-screenrecord-raw.mp4"
FINAL="/Users/hiteshvenu/dejaVu/dejavu-demo-final-50s.mp4"
BLACK_WP="/System/Library/Desktop Pictures/Solid Colors/Black.png"

# Save current wallpaper so we can restore it
ORIG_WP=$(osascript -e 'tell application "Finder" to get POSIX path of (get desktop picture as alias)' 2>/dev/null || echo "")

cleanup() {
  # Restore original wallpaper
  if [[ -n "$ORIG_WP" ]]; then
    osascript -e "tell application \"Finder\" to set desktop picture to POSIX file \"$ORIG_WP\"" 2>/dev/null || true
  fi
}
trap cleanup EXIT

rm -f "$RAW" "$FINAL"

echo "0/3  Setting clean desktop..."
osascript -e "tell application \"Finder\" to set desktop picture to POSIX file \"$BLACK_WP\""
sleep 0.5

echo "1/3  Opening Terminal and launching demo..."
osascript -e 'tell application "Terminal" to activate'
sleep 0.4

# Position window at y=0 so it covers the menu bar area
osascript -e 'tell application "Terminal" to set bounds of front window to {0, 0, 1440, 900}'
sleep 0.3

# Clear any previous title and set a clean one
osascript -e 'tell application "Terminal" to tell front window to set custom title to "dejavu"'
sleep 0.3

# Clear the shell
osascript -e 'tell application "Terminal" to do script "clear" in front window'
sleep 0.5

# Launch demo in the same window
osascript -e 'tell application "Terminal" to do script "cd ~/dejaVu && bash record_demo.sh" in front window'
sleep 1   # let header appear on screen before recording starts

echo "2/3  Recording for 110s (auto-stops)..."
ffmpeg -f avfoundation \
  -framerate 30 \
  -i "2" \
  -t 110 \
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
