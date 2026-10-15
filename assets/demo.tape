# Rebuild the README demo: vhs assets/demo.tape (from the repository root)
Output assets/demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1400
Set Height 470
Set Padding 24
Set TypingSpeed 35ms
Set Theme { "name": "baton", "background": "#0D1117", "foreground": "#E6EDF3", "cursor": "#FF922B", "selection": "#30363D", "black": "#161B22", "brightBlack": "#9198A1", "red": "#F85149", "brightRed": "#FF7B72", "green": "#3FB950", "brightGreen": "#56D364", "yellow": "#FF922B", "brightYellow": "#FFA657", "blue": "#91A7FF", "brightBlue": "#A5B4FC", "magenta": "#D2A8FF", "brightMagenta": "#E2C5FF", "cyan": "#76E3EA", "brightCyan": "#B3F0FF", "white": "#E6EDF3", "brightWhite": "#FFFFFF" }

Hide
Type "export PS1='$ ' && cd $(mktemp -d) && git init -q && baton init --roles frontend,backend,qa >/dev/null && clear"
Enter
Sleep 1s
Show

Type "# frontend asks backend a question"
Sleep 200ms
Enter
Type `baton post Q --as frontend --to backend --title "Which route serves health?" "For the status page."`
Sleep 300ms
Enter
Sleep 1.5s

Type "# backend tries to hand off with the question still open"
Sleep 200ms
Enter
Type `baton handoff --as backend --phase S1-A --state DONE --to qa --title "S1-A backend" "Health endpoint done."`
Sleep 300ms
Enter
Sleep 3s

Type "# backend answers and closes it"
Sleep 200ms
Enter
Type `baton reply Q-001 --as backend --close "Use GET /api/health."`
Sleep 300ms
Enter
Sleep 1.5s

Type "# now the hand-off goes through"
Sleep 200ms
Enter
Type `baton handoff --as backend --phase S1-A --state DONE --to qa --title "S1-A backend" "Health endpoint done."`
Sleep 300ms
Enter
Sleep 2s

Type "# the status table, for humans"
Sleep 200ms
Enter
Type "baton status"
Sleep 300ms
Enter
Sleep 4s
