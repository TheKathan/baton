# The README's agent demos

`assets/agent-demo.gif`, the README hero, is two real agents from different vendors on one board: Codex (frontend) asks a question, and Claude Code (backend) is refused, answers and hands off. `assets/agent-demo-claude.gif`, used in the getting-started guide, is one Claude Code agent. Neither agent gets the baton skill or a hint about refusals: their briefs only name the command to run.

## Two vendors (`duo/`)

Needs tmux, VHS, ffmpeg, Python 3 with numpy and Pillow, and logged-in Codex and Claude Code. From `duo/`: `vhs tape.tape` writes `raw.gif`; extract its frames, run `mask.py` to hide Claude Code's plan name, re-encode, then add the caption bar with `edit/` as below. `codex-frontend.sh` lets Codex read only the scratch project and baton's install.

## One agent

Needs [VHS](https://github.com/charmbracelet/vhs), ffmpeg, Python 3 with Pillow, a logged-in Claude Code, and baton linked at `/opt/homebrew/bin/baton` (so no home path shows on screen).

1. Record a take (about $0.10; every take differs a little):

   ```bash
   cd scripts/agent-demo && vhs agent-demo.tape    # writes raw.gif, runs in ~/health-service
   ```

2. Trim it to the first 14 s, mask Claude Code's status rows and encode:

   ```bash
   mkdir p && ffmpeg -t 14 -i raw.gif -vf fps=10 p/r%03d.png
   python3 mask.py p 740
   ffmpeg -framerate 10 -i p/m%03d.png -vf "split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=none" edit/source.gif
   ```

3. Add the caption bar, outlines, holds and the 1.5× stretch:

   ```bash
   edit/build.sh    # writes edit/final.gif; copy it to assets/agent-demo.gif
   ```

   The timeline in `edit/build.sh`, the outline positions in `edit/captions.py` and the box that masks the account's plan name in Claude Code's header all match the current take. Adjust them to a new take.

Check every frame before publishing: no username, no `/Users/…` or `/private/var/…` paths, no session title, and no account plan name. Delete `~/health-service`, `raw.gif` and the frame folders afterwards.
