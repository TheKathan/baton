#!/usr/bin/env python3
"""Build assets/how-it-works-animated-{dark,light}.svg: the README's "How it works" animation.

frontend asks backend a question; backend's hand-off is refused while it is open; backend
answers and the hand-off goes through as H-002. Every message is a typed entry in the
append-only log.

    python3 scripts/animate_how_it_works.py

Every element's base style is its FINAL state; the CSS keyframes only
replay how it got there, so reduced motion shows the finished diagram.
"""
from pathlib import Path

LOOP = 12000    # ms
OUT_AT = 11300  # animated elements start fading out here
OUT_END = 11650

THEMES = {
    "dark": {"canvas": "#161B22", "surface": "#0D1117", "chip": "#1B2230", "line": "#30363D",
                 "text": "#E6EDF3", "muted": "#9198A1", "ind": "#91A7FF", "indp": "#1A2142",
                 "org": "#F76707", "orgt": "#FF922B", "orgp": "#2B1D10", "ok": "#3FB950", "bad": "#F85149"},
    "light": {"canvas": "#F6F8FA", "surface": "#FFFFFF", "chip": "#EEF1F4", "line": "#D0D7DE",
                  "text": "#1F2328", "muted": "#59636E", "ind": "#3B5BDB", "indp": "#EDF2FF",
                  "org": "#F76707", "orgt": "#C2410C", "orgp": "#FFF4E6", "ok": "#1A7F37", "bad": "#CF222E"},
}

SANS = 'ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'
MONO = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'

# ---- timeline (ms) ----
T_Q = 400         # frontend posts Q-001
T_Q_LOG = 1000
T_TRY = 2200      # backend tries to hand off
T_REFUSE = 3000   # baton intercepts
T_REPLY = 5200    # backend answers
T_REPLY_LOG = 5800
T_H = 7200        # hand-off H-002
T_H_LOG = 7600
T_QA = 8600       # qa takes over, the baton moves to qa
T_QA_CUR = 9000
T_SUMMARY = 10000

KEYFRAMES = []
NAMES = []


def pct(ms):
    return f"{ms / LOOP * 100:.2f}%"


def appear(name, t, dur=450, rise=True):
    """Hidden until t, eases in, stays until the loop fade-out."""
    off = "opacity:0;transform:translateY(8px)" if rise else "opacity:0"
    on = "opacity:1;transform:translateY(0)" if rise else "opacity:1"
    KEYFRAMES.append(
        f"@keyframes {name}{{0%,{pct(t)}{{{off}}}{pct(t + dur)},{pct(OUT_AT)}{{{on}}}"
        f"{pct(OUT_END)},100%{{{off}}}}}")
    NAMES.append(name)


def window(name, t0, t1):
    """Visible only between t0 and t1 (base style: hidden). 250 ms in, 300 ms out."""
    KEYFRAMES.append(
        f"@keyframes {name}{{0%,{pct(t0)}{{opacity:0}}{pct(t0 + 250)},{pct(t1)}{{opacity:1}}"
        f"{pct(t1 + 300)},100%{{opacity:0}}}}")
    NAMES.append(name)


def window_from_start(name, t1):
    """Visible from loop start to t1, fades back in at the very end of the loop."""
    KEYFRAMES.append(
        f"@keyframes {name}{{0%,{pct(t1)}{{opacity:1}}{pct(t1 + 300)},{pct(11800)}{{opacity:0}}"
        f"100%{{opacity:1}}}}")
    NAMES.append(name)


def pulses(name, times, up=150, down=700):
    steps = "".join(f"{pct(t - 50)}{{opacity:0}}{pct(t + up)}{{opacity:1}}{pct(t + down)}{{opacity:0}}"
                    for t in times)
    KEYFRAMES.append(f"@keyframes {name}{{0%{{opacity:0}}{steps}100%{{opacity:0}}}}")
    NAMES.append(name)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(c):
    KEYFRAMES.clear()
    NAMES.clear()
    o = []
    a = o.append

    def text(x, y, s, cls, fill, anchor=None):
        an = f' text-anchor="{anchor}"' if anchor else ""
        a(f'<text x="{x}" y="{y}" class="{cls}" fill="{fill}"{an}>{esc(s)}</text>')

    def chip(x, y, label, color, w=None):
        w = w or (len(label) * 8.6 + 16)
        a(f'<rect x="{x}" y="{y}" width="{w}" height="21" rx="4" fill="{c["chip"]}" stroke="{c["line"]}"/>')
        text(x + w / 2, y + 15.5, label, "m b14", color, "middle")
        return w

    def baton_glyph(cx, cy, size=1.0, fill=None):
        w, h = 18 * size, 6 * size
        a(f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" rx="{h / 2}" '
          f'fill="{fill or c["org"]}" transform="rotate(-35 {cx} {cy})"/>')

    def avatar(cy, initials):
        a(f'<circle cx="64" cy="{cy}" r="17" fill="{c["indp"]}" stroke="{c["ind"]}"/>')
        text(64, cy + 5, initials, "s b14", c["ind"], "middle")

    BX, BW, BH = 96, 600, 54

    def bubble(y, who, kind, to, msg, right=None, right_fill=None, msg_fill=None):
        a(f'<rect x="{BX}" y="{y}" width="{BW}" height="{BH}" rx="12" fill="{c["surface"]}" stroke="{c["line"]}"/>')
        text(112, y + 22, who, "s b14", c["text"])
        cw = chip(186, y + 6, kind, c["ind"])
        if to:
            text(186 + cw + 10, y + 22, to, "s r14", c["muted"])
        text(112, y + 44, msg, "s r15", msg_fill or c["text"])
        if right:
            text(BX + BW - 16, y + 22, right, "m r14", right_fill or c["muted"], "end")

    W, H = 1200, 506
    a(f'<rect width="{W}" height="{H}" fill="{c["canvas"]}"/>')

    # ---- header: wordmark + per-beat caption ----
    baton_glyph(50, 34, 1.0)
    text(66, 41, "baton", "s b20", c["orgt"])
    caps = [
        ("c0", "frontend asks backend a question", None, T_TRY - 300),
        ("c1", "backend tries to hand off to qa", T_TRY, T_REFUSE - 300),
        ("c2", "backend's hand-off is refused: Q-001 is unanswered", T_REFUSE, T_REPLY - 300),
        ("c3", "backend answers Q-001", T_REPLY, T_H - 300),
        ("c4", "the hand-off goes through as H-002", T_H, T_QA - 300),
        ("c5", "qa takes over S1-A and reads each event once", T_QA, T_SUMMARY - 300),
    ]
    for cls, s, t0, t1 in caps:
        a(f'<g class="{cls}" opacity="0">')
        text(140, 40, s, "s r15", c["text"] if cls == "c2" else c["muted"])
        a('</g>')
        if t0 is None:
            window_from_start(cls, t1)
        else:
            window(cls, t0, t1)
    a('<g class="cs">')
    text(140, 40, "Every message is a typed entry; a hand-off waits for its questions to be answered.",
         "s r15", c["muted"])
    a('</g>')
    appear("cs", T_SUMMARY, 300, rise=False)

    # rows
    y1, y2, yn, y3, y4, y5 = 62, 128, 214, 300, 366, 432

    a(f'<line x1="64" y1="72" x2="64" y2="{y5 + 20}" stroke="{c["line"]}" stroke-width="2"/>')

    # ---- row 1: frontend posts Q-001 ----
    a('<g class="r1">')
    avatar(y1 + 27, "FE")
    bubble(y1, "frontend", "Q-001", "to backend", "Which route serves the health check?", "#1 in log")
    a('</g>')
    appear("r1", T_Q)

    # ---- row 2: backend tries to hand off (refused) ----
    a('<g class="r2">')
    avatar(y2 + 27, "BE")
    text(112, y2 + BH + 20, "baton handoff --as backend --phase S1-A --state DONE --to qa …", "m r14", c["muted"])
    a('</g>')
    appear("r2", T_TRY)
    a('<g class="r2b">')
    bubble(y2, "backend", "H", "to qa", "Health endpoint done, handing off to qa.")
    a('</g>')
    KEYFRAMES.append(
        f"@keyframes r2b{{0%,{pct(T_TRY)}{{opacity:0;transform:translateY(8px)}}"
        f"{pct(T_TRY + 450)},{pct(T_REFUSE + 200)}{{opacity:1;transform:translateY(0)}}"
        f"{pct(T_REFUSE + 700)},{pct(OUT_AT)}{{opacity:.82;transform:translateY(0)}}"
        f"{pct(OUT_END)},100%{{opacity:0;transform:translateY(8px)}}}}")
    NAMES.append("r2b")
    a('<g class="r2x">')
    a(f'<line x1="110" y1="{y2 + 39}" x2="{112 + 282}" y2="{y2 + 39}" stroke="{c["bad"]}" stroke-width="2"/>')
    text(BX + BW - 16, y2 + 22, "refused, not in log", "m r14", c["bad"], "end")
    a(f'<rect x="{BX}" y="{y2}" width="{BW}" height="{BH}" rx="12" fill="none" stroke="{c["bad"]}" stroke-width="1.5"/>')
    a('</g>')
    appear("r2x", T_REFUSE, 300, rise=False)

    # ---- baton's refusal notice ----
    a('<g class="rn">')
    a(f'<circle cx="64" cy="{yn + 30}" r="17" fill="{c["orgp"]}" stroke="{c["org"]}"/>')
    baton_glyph(64, yn + 30, 1.0)
    a(f'<rect x="{BX}" y="{yn}" width="{BW}" height="74" rx="12" fill="{c["orgp"]}" stroke="{c["org"]}"/>')
    text(112, yn + 22, "baton", "s b14", c["orgt"])
    text(162, yn + 22, "to backend", "s r14", c["muted"])
    a(f'<text x="112" y="{yn + 44}" class="m r14"><tspan fill="{c["orgt"]}" font-weight="700">baton:</tspan>'
      f'<tspan fill="{c["bad"]}" font-weight="700"> hand-off refused:</tspan></text>')
    text(112, yn + 64, "- unanswered threads addressed to you: Q-001", "m r14", c["text"])
    a('</g>')
    appear("rn", T_REFUSE + 150)

    # ---- row 3: backend answers ----
    a('<g class="r3">')
    avatar(y3 + 27, "BE")
    bubble(y3, "backend", "reply Q-001", None, "GET /api/health, defined in src/routes.js.", "#2 in log")
    a('</g>')
    appear("r3", T_REPLY)

    # ---- row 4: hand-off H-002 lands ----
    a('<g class="r4">')
    avatar(y4 + 27, "BE")
    bubble(y4, "backend", "H-002", "to qa", "S1-A backend → qa: health check ready to test.")
    a('</g>')
    appear("r4", T_H)
    a('<g class="r4ok">')
    text(BX + BW - 16, y4 + 22, "posted H-002 · #3", "m b14", c["ok"], "end")
    a(f'<rect x="{BX}" y="{y4}" width="{BW}" height="{BH}" rx="12" fill="none" stroke="{c["ok"]}" stroke-width="1.5"/>')
    a('</g>')
    appear("r4ok", T_H_LOG, 300, rise=False)

    # ---- row 5: qa takes over ----
    a('<g class="r5">')
    avatar(y5 + 27, "QA")
    a(f'<rect x="{BX}" y="{y5}" width="{BW}" height="{BH}" rx="12" fill="{c["surface"]}" stroke="{c["line"]}"/>')
    text(112, y5 + 22, "qa", "s b14", c["text"])
    text(140, y5 + 22, "takes over H-002", "s r14", c["muted"])
    text(112, y5 + 44, "Read once via my cursor. Testing GET /api/health.", "s r15", c["text"])
    text(BX + BW - 16, y5 + 22, "cursor ▸ 3", "m r14", c["muted"], "end")
    a('</g>')
    appear("r5", T_QA)

    # ---- the baton holder pill: backend's rows, then qa ----
    PW = 82
    px, py = BX + BW - 16 - PW, y5 + 29
    a('<g class="hp">')
    a(f'<rect x="{px}" y="{py}" width="{PW}" height="21" rx="10.5" fill="{c["orgp"]}" stroke="{c["org"]}"/>')
    baton_glyph(px + 16, py + 10.5, 0.7)
    text(px + 29, py + 15.5, "baton", "s b14", c["orgt"])
    a('</g>')
    d_try, d_rep, d_h = y2 - y5, y3 - y5, y4 - y5

    def tr(dy):
        return f"transform:translateY({dy}px)"
    KEYFRAMES.append(
        "@keyframes hp{"
        f"0%,{pct(T_TRY + 200)}{{opacity:0;{tr(d_try)}}}"
        f"{pct(T_TRY + 650)},{pct(T_REPLY)}{{opacity:1;{tr(d_try)}}}"
        f"{pct(T_REPLY + 600)},{pct(T_H)}{{opacity:1;{tr(d_rep)}}}"
        f"{pct(T_H + 600)},{pct(T_QA)}{{opacity:1;{tr(d_h)}}}"
        f"{pct(T_QA + 600)},{pct(OUT_AT)}{{opacity:1;{tr(0)}}}"
        f"{pct(OUT_END)},100%{{opacity:0;{tr(0)}}}}}")
    NAMES.append("hp")

    # ---- right: append-only log ----
    LX, LW, LY = 740, 420, 62
    a(f'<rect x="{LX}" y="{LY}" width="{LW}" height="214" rx="12" fill="{c["surface"]}" stroke="{c["line"]}"/>')
    a(f'<text x="{LX + 18}" y="{LY + 27}" class="m r14"><tspan fill="{c["muted"]}">.baton/events/</tspan>'
      f'<tspan fill="{c["text"]}" font-weight="700">S1.jsonl</tspan></text>')
    CW = 142
    fx, fy = LX + LW - 16 - CW, LY + 11
    a(f'<rect x="{fx}" y="{fy}" width="{CW}" height="23" rx="11.5" fill="{c["orgp"]}" stroke="{c["line"]}"/>')
    a(f'<rect class="lk" x="{fx}" y="{fy}" width="{CW}" height="23" rx="11.5" fill="none" stroke="{c["org"]}" stroke-width="2" opacity="0"/>')
    a(f'<rect x="{fx + 12}" y="{fy + 10}" width="10" height="8" rx="1.5" fill="{c["org"]}"/>')
    a(f'<path d="M{fx + 14} {fy + 10}v-2.5a3 3 0 0 1 6 0v2.5" fill="none" stroke="{c["org"]}" stroke-width="1.6"/>')
    text(fx + 30, fy + 16.5, "locked write", "m r14", c["orgt"])
    pulses("lk", [T_Q_LOG, T_REPLY_LOG, T_H_LOG])
    text(LX + 18, LY + 52, "append-only · one line per write · ids never reused", "s r14", c["muted"])
    a(f'<line x1="{LX + 18}" y1="{LY + 64}" x2="{LX + LW - 18}" y2="{LY + 64}" stroke="{c["line"]}"/>')

    rows = [
        (1, "Q-001", "frontend → backend", T_Q_LOG, "l1"),
        (2, "reply", "backend re Q-001", T_REPLY_LOG, "l2"),
        (3, "H-002", "S1-A backend → qa", T_H_LOG, "l3"),
    ]
    for i, (seq, kind, desc, t, cls) in enumerate(rows):
        ry = LY + 72 + i * 36
        a(f'<g class="{cls}">')
        a(f'<rect x="{LX + 10}" y="{ry}" width="{LW - 20}" height="32" rx="6" fill="{c["indp"]}" class="{cls}h" opacity="0"/>')
        text(LX + 26, ry + 21, str(seq), "m r14", c["muted"])
        chip(LX + 48, ry + 5.5, kind, c["ind"], 72)
        text(LX + 134, ry + 21, desc, "m r14", c["text"])
        a('</g>')
        appear(cls, t, 350)
        pulses(cls + "h", [t], 150, 1100)
    # ghost of the refused write, in row 2's slot before row 2 exists
    gy = LY + 72 + 36
    a(f'<g class="gh" opacity="0"><rect x="{LX + 10}" y="{gy}" width="{LW - 20}" height="32" rx="6" fill="none" '
      f'stroke="{c["bad"]}" stroke-dasharray="5 4"/>')
    text(LX + 26, gy + 21, "H refused · nothing appended", "m r14", c["bad"])
    a('</g>')
    window("gh", T_REFUSE + 100, T_REPLY - 400)
    # qa read cursor
    a(f'<line x1="{LX + 18}" y1="{LY + 184}" x2="{LX + LW - 18}" y2="{LY + 184}" stroke="{c["line"]}" stroke-dasharray="3 4"/>')
    a('<g class="cu">')
    text(LX + 26, LY + 204, "read cursor", "s r14", c["muted"])
    text(LX + 134, LY + 204, "qa ▸ 3 · each event read once", "m r14", c["text"])
    a('</g>')
    appear("cu", T_QA_CUR, 350, rise=False)

    # ---- right: generated views ----
    SY = 290
    a(f'<rect x="{LX}" y="{SY}" width="{LW}" height="88" rx="12" fill="{c["surface"]}" stroke="{c["line"]}"/>')
    a(f'<rect class="sf" x="{LX}" y="{SY}" width="{LW}" height="88" rx="12" fill="none" stroke="{c["ind"]}" stroke-width="1.5" opacity="0"/>')
    a(f'<text x="{LX + 18}" y="{SY + 26}" class="m r14"><tspan fill="{c["text"]}" font-weight="700">STATUS.md</tspan>'
      f'<tspan fill="{c["muted"]}"> + BOARD.md</tspan></text>')
    text(LX + LW - 18, SY + 26, "rewritten after every write", "s r14", c["muted"], "end")
    sy = SY + 64
    st = [
        ("s0", "no open threads · backend holds S1-A", c["muted"]),
        ("s1", "Q-001 open → backend · backend holds S1-A", c["orgt"]),
        ("s2", "Q-001 answered · backend holds S1-A", c["text"]),
        ("s3", "H-002 accepted · qa holds S1-A", c["ok"]),
    ]
    for cls, s, col in st:
        op = "" if cls == "s3" else ' opacity="0"'
        a(f'<g class="{cls}"{op}>')
        a(f'<circle cx="{LX + 24}" cy="{sy - 5}" r="4" fill="{col}"/>')
        text(LX + 38, sy, s, "s b15", c["text"])
        a('</g>')
    window_from_start("s0", T_Q_LOG)
    window("s1", T_Q_LOG + 300, T_REPLY_LOG)
    window("s2", T_REPLY_LOG + 300, T_H_LOG)
    appear("s3", T_H_LOG + 300, 250, rise=False)
    pulses("sf", [T_Q_LOG + 300, T_REPLY_LOG + 300, T_H_LOG + 300], 150, 900)

    # ---- right: the rule (glows at the refusal) ----
    RY, RH = 392, 94
    a(f'<rect x="{LX}" y="{RY}" width="{LW}" height="{RH}" rx="12" fill="{c["canvas"]}" stroke="{c["line"]}" stroke-dasharray="4 4"/>')
    a(f'<rect class="rg" x="{LX}" y="{RY}" width="{LW}" height="{RH}" rx="12" fill="{c["orgp"]}" stroke="{c["org"]}" stroke-width="2" opacity="0"/>')
    window("rg", T_REFUSE + 150, T_REPLY - 500)
    text(LX + 18, RY + 30, "The rule", "s b14", c["orgt"])
    text(LX + 18, RY + 56, "No hand-off while a question addressed", "s r15", c["text"])
    text(LX + 18, RY + 78, "to you is still unanswered.", "s r15", c["text"])

    css = (
        f".s{{font-family:{SANS}}}.m{{font-family:{MONO}}}"
        ".r14{font-size:14px}.r15{font-size:15px}"
        ".b14{font-weight:700;font-size:14px}.b15{font-weight:600;font-size:15px}"
        ".b20{font-weight:800;font-size:20px;letter-spacing:-.3px}"
        ".r2b{opacity:.82}"
    )
    anim = "".join(f".{n}{{animation:{n} {LOOP}ms linear infinite both}}" for n in NAMES)
    ease = ".r1,.r2,.r2b,.r3,.r4,.r5,.l1,.l2,.l3,.hp{animation-timing-function:cubic-bezier(.2,.7,.2,1)}"
    reduce = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    style = css + anim + ease + "".join(KEYFRAMES) + reduce

    title = "How baton works: a hand-off is refused until the question is answered"
    desc = ("A chat-like thread between three AI agents, where every message is a typed entry appended "
            "to .baton/events/S1.jsonl under a file lock. frontend asks backend Q-001: which route serves "
            "the health check? backend tries to hand off S1-A to qa and baton refuses: 'baton: hand-off "
            "refused: - unanswered threads addressed to you: Q-001'; nothing is written. backend replies "
            "GET /api/health, defined in src/routes.js, then hand-off H-002 is posted, the baton moves to "
            "qa, and qa reads it once via its cursor. STATUS.md updates after every write.")
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-labelledby="t d"><title id="t">{esc(title)}</title><desc id="d">{esc(desc)}</desc>'
            f'<style>{style}</style>')
    return head + "".join(o) + "</svg>\n"


if __name__ == "__main__":
    assets = Path(__file__).resolve().parent.parent / "assets"
    for name, colors in THEMES.items():
        p = assets / f"how-it-works-animated-{name}.svg"
        p.write_text(build(colors), encoding="utf-8")
        print(p.name, p.stat().st_size, "bytes")
