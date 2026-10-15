# Tight take: a real, unscripted Claude Code (Sonnet) run on a baton board, with a brief that names the
# exact hand-off command. Run from this folder:  vhs tape.tape
# then trim, mask and caption it (see README.md in this folder).
Output raw.gif

Set Shell "bash"
Set FontSize 19
Set Width 1200
Set Height 800
Set Padding 20
Set TypingSpeed 30ms
Set Theme { "name": "baton", "background": "#0D1117", "foreground": "#E6EDF3", "cursor": "#FF922B", "selection": "#30363D", "black": "#161B22", "brightBlack": "#9198A1", "red": "#F85149", "brightRed": "#FF7B72", "green": "#3FB950", "brightGreen": "#56D364", "yellow": "#FF922B", "brightYellow": "#FFA657", "blue": "#91A7FF", "brightBlue": "#A5B4FC", "magenta": "#D2A8FF", "brightMagenta": "#E2C5FF", "cyan": "#76E3EA", "brightCyan": "#B3F0FF", "white": "#E6EDF3", "brightWhite": "#FFFFFF" }

Hide
Type "unset $(env | grep -o '^CLAUDE[A-Z_]*') && export PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin && export PS1='$ ' && ./setup.sh $HOME/health-service && clear"
Enter
Sleep 2s
Type `cd $HOME/health-service && clear && $HOME/.local/bin/claude --model sonnet --disable-slash-commands --strict-mcp-config --setting-sources project --permission-mode default --allowedTools Bash Read --disallowedTools Grep Glob -- 'You are the backend agent on this project. S1-A, the health endpoint in src/, is done. Hand off S1-A to qa now: baton handoff --as backend --phase S1-A --state DONE --to qa --title "S1-A backend" "Health endpoint done."'`
Enter
Wait+Screen@60s /I trust this folder|esc to interrupt/
Sleep 1.5s
Down
Sleep 700ms
Enter
Sleep 1s
Show

Sleep 45s
