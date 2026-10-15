# The README's agent demo

`assets/agent-demo.gif` is a real, unscripted Claude Code (Sonnet) session on a baton board, trimmed and captioned. The agent plays backend and gets no baton skill: its brief only names the hand-off command, and baton's refusal tells it what to do.

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
