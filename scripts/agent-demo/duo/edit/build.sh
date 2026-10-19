#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python3 captions.py
python3 palette.py

CAP="-loop 1 -framerate 25 -t 21 -i"
ffmpeg -v error -y -i source.gif \
  $CAP caps/c1.png $CAP caps/c2.png $CAP caps/c3.png $CAP caps/c4.png -i caps/palette.png \
  -filter_complex "
[0:v]format=rgb24,setsar=1,pad=1240:870:0:40:color=0x0D1117[v];
[v][1:v]overlay=0:0:format=rgb:enable='lt(t,8.6)'[o1];
[o1][2:v]overlay=0:0:format=rgb:enable='between(t,8.6,15.72)'[o2];
[o2][3:v]overlay=0:0:format=rgb:enable='between(t,15.72,17.8)'[o3];
[o3][4:v]overlay=0:0:format=rgb:enable='gte(t,17.8)'[o4];
[o4][5:v]paletteuse=dither=none
" -loop 0 final.gif

mkdir -p frames
for spec in "5.0:1-codex-posts-Q-001" "10.5:2-claude-refused" "16.5:3-answered-H-002" "20.5:4-two-vendors-one-board"; do
  ffmpeg -v error -y -ss "${spec%%:*}" -i final.gif -frames:v 1 "frames/${spec#*:}.png"
done
ffprobe -v error -show_entries format=duration,size -of default=nw=1 final.gif
