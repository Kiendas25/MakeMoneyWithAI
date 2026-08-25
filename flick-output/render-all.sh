#!/usr/bin/env bash
set -euo pipefail
CHROME=/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell
cd "$(dirname "$0")/remotion"
for id in promise-flash empty-toolbox star-ranked-scroll rapid-fire-cards monetize-annotation pick-one-ship-it; do
  mkdir -p "../scenes/$id"
  echo "=== render $id ==="
  npx remotion render src/index.tsx "$id" "../scenes/$id/$id.mp4" \
    --browser-executable="$CHROME" --concurrency=4 --log=error
  npx remotion still src/index.tsx "$id" "../scenes/$id/poster.jpg" \
    --frame=$((30)) --browser-executable="$CHROME" --image-format=jpeg --quality=90
  echo "=== done $id ==="
done
echo "ALL SCENES RENDERED"
