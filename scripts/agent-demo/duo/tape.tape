# Usage, from this folder: vhs tape.tape   (then mask.py and the caption pass; see ../README.md)
Output raw.gif

Set Shell "bash"
Set FontSize 18
Set Width 1240
Set Height 900
Set Padding 18
Set Framerate 25
Set TypingSpeed 16ms
Set Theme { "name": "baton", "background": "#0D1117", "foreground": "#E6EDF3", "cursor": "#FF922B", "selection": "#30363D", "black": "#161B22", "brightBlack": "#9198A1", "red": "#F85149", "brightRed": "#FF7B72", "green": "#3FB950", "brightGreen": "#56D364", "yellow": "#FF922B", "brightYellow": "#FFA657", "blue": "#91A7FF", "brightBlue": "#A5B4FC", "magenta": "#D2A8FF", "brightMagenta": "#E2C5FF", "cyan": "#76E3EA", "brightCyan": "#B3F0FF", "white": "#E6EDF3", "brightWhite": "#FFFFFF" }

Hide
Type "unset $(env | grep -o '^CLAUDE[A-Z_]*') && export PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin && export PS1='$ ' BASH_SILENCE_DEPRECATION_WARNING=1 W=$PWD P=$HOME/health-service-duo && ./setup.sh $P && cd $P && clear"
Enter
Sleep 2s
Type `tmux -L batondemo -f $W/tmux.conf new -s demo -c $P "$W/codex-frontend.sh $P" \; set -p @label "frontend · Codex" \; split-window -v -l 6 -c $P "$W/board-strip.sh" \; set -p @label "live board · baton list" \; select-pane -U \; split-window -h -l 50% -c $P "$W/claude-backend.sh $P" \; set -p @label "backend · Claude Code" \; select-pane -L`
Enter
Wait+Screen@60s /OpenAI Codex/
Sleep 300ms
Show

Sleep 70s

Hide
Ctrl+B
Type ":kill-server"
Enter
Sleep 500ms
