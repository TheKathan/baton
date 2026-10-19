#!/bin/bash
# Usage: board-strip.sh <dir>   (the live board strip)
O=$'\e[33m'; G=$'\e[32m'; C=$'\e[36m'; D=$'\e[90m'; B=$'\e[1m'; R=$'\e[0m'
clear; tput civis; HOME_=$(tput cup 0 0); ED=$(tput ed)
draw() {
  out=$(baton list 2>/dev/null)
  [ -z "$out" ] && { echo "${D}(empty board)${R}"; return; }
  while IFS= read -r l; do
    id=${l:1:5}
    IFS='|' read -r i who st title <<<"$(sed -E 's/^\[([A-Z]-[0-9]+)\] (.*) · (OPEN|CLOSED) · [0-9-]+ [0-9:]+ · (.*)/\1|\2|\3|\4/' <<<"$l")"
    echo "${O}${B}[$i]${R} $who · ${G}$st${R} · $title"
    baton show "$id" | grep '^> \[A\]' | sed -E "s/^> \[A\] ([a-z]+) · [0-9-]+ [0-9:]+: (.*)/        ${C}↳ \1: \2${R}/"
  done <<<"$out"
}
while :; do o=$(draw); printf '%s%s%s' "$HOME_" "$ED" "$o"; sleep 0.5; done
