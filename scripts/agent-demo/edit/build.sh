#!/usr/bin/env bash
# Trim + caption pass over the "tight" take (source.gif, 1200x740, 10 fps).
# Adds a 40 px caption bar above the footage, two outlines, a 2x stretch and holds.
# Agent output is never altered; no crop, no zoom.
set -euo pipefail
cd "$(dirname "$0")"

python3 captions.py   # renders caps/*.png
python3 palette.py    # caps/palette.png: source colours kept exactly

# Output timeline (s):  0-2.5 hold refusal | 2.5-3.5 src 0-1.0 | 3.5-7.83 src 1.0-7.5 at 1.5x
#   7.83-8.23 src 7.5-7.9 | 8.23-10.23 hold H-002 frame | 10.23-11.73 src 7.9-9.4
#   11.73-14.73 src 9.4-12.4 | 14.73-16.73 hold the final message
# The header's plan name ("Claude Enterprise") is covered with the terminal background while it is on screen (src < 6.15 s).
CAP="-loop 1 -framerate 10 -t 16.73 -i"
ffmpeg -v error -y -i source.gif \
  $CAP caps/c1.png $CAP caps/c2.png $CAP caps/c2_fast.png $CAP caps/c3.png $CAP caps/c4.png $CAP caps/box_red.png $CAP caps/box_orange.png -i caps/palette.png \
  -filter_complex "
[0:v]format=rgb24,setsar=1,drawbox=x=285:y=42:w=249:h=26:color=0x0D1016:t=fill:enable='lt(t,6.15)',split=8[a][b][c][d][e][f][g][h];
[a]trim=start=0:duration=0.1,setpts=PTS-STARTPTS,loop=loop=24:size=1:start=0,setpts=N/10/TB[s1];
[b]trim=0:1.0,setpts=PTS-STARTPTS[s2];
[c]trim=1.0:7.5,setpts=(PTS-STARTPTS)/1.5,fps=10[s3];
[d]trim=7.5:7.9,setpts=PTS-STARTPTS[s4];
[e]trim=start=7.9:duration=0.1,setpts=PTS-STARTPTS,loop=loop=19:size=1:start=0,setpts=N/10/TB[s5];
[f]trim=7.9:9.4,setpts=PTS-STARTPTS[s6];
[g]trim=9.4:12.4,setpts=PTS-STARTPTS[s7];
[h]trim=start=12.3:duration=0.1,setpts=PTS-STARTPTS,loop=loop=19:size=1:start=0,setpts=N/10/TB[s8];
[s1][s2][s3][s4][s5][s6][s7][s8]concat=n=8:v=1:a=0,fps=10,
  pad=1200:780:0:40:color=0x0D1117[v0];
[v0][6:v]overlay=76:304:format=rgb:shortest=1:enable='between(t,0.3,3.5)'[v1];
[v1][7:v]overlay=76:597:format=rgb:enable='between(t,8.23,11.73)'[v];
[v][1:v]overlay=0:0:format=rgb:enable='lt(t,3.5)'[o1];
[o1][2:v]overlay=0:0:format=rgb:enable='between(t,7.83,8.23)'[o2];
[o2][3:v]overlay=0:0:format=rgb:enable='between(t,3.5,7.83)'[o3];
[o3][4:v]overlay=0:0:format=rgb:enable='between(t,8.23,11.73)'[o4];
[o4][5:v]overlay=0:0:format=rgb:enable='gte(t,11.73)'[o5];
[o5][8:v]paletteuse=dither=none
" -loop 0 final.gif

mkdir -p frames
for spec in "1.0:1-refusal-caption" "7.9:2-answer" "9.0:3-handoff-outline" "15.0:4-final"; do
  ffmpeg -v error -y -ss "${spec%%:*}" -i final.gif -frames:v 1 "frames/${spec#*:}.png"
done
ffprobe -v error -show_entries format=duration,size -of default=nw=1 final.gif
