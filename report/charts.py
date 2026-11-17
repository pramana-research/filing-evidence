"""Static SVG charts for the paper and the model pages. Every value comes from the data dict (stats.compute()).

Colours (validated for colour-vision deficiency and contrast against the site surface #FAFAF7):
  outcomes, a diverging scale from good to bad with a neutral midpoint:
    correct #2E3F9E · right value, unusable evidence #8592D6 · missed #D9D6CE · caught wrong #E57C62 ·
    confident wrong #B3302A
  setups, one hue light to dark: C1 #8F9BDD · C2 #5466C4 · C3 #1F2C73
Marks carry colour; text uses ink tokens. Every mark has a <title> (hover) and each figure has a data table.
"""

from __future__ import annotations

import math
from html import escape

OUT = {"correct": "#2E3F9E", "unverifiable_right": "#8592D6", "missed": "#D9D6CE", "caught_wrong": "#E57C62",
       "confident_wrong": "#B3302A", "invalid": "#A7A398"}
OUT_ORDER = ["correct", "unverifiable_right", "missed", "invalid", "caught_wrong", "confident_wrong"]
SETUP = {"C1": "#8F9BDD", "C2": "#5466C4", "C3": "#1F2C73"}
SETUP_NAME = {"C1": "Plain", "C2": "Check + retry", "C3": "Thinking"}
INK, INK2, MUTED, GRID, AXIS, SURF = "#12161C", "#3D4452", "#5B6472", "#E7E8E3", "#C3C8D2", "#FAFAF7"
GOOD, BAD = "#2E3F9E", "#B3302A"

NAMES = {
    "qwen3.5-9b": "Qwen3.5-9B", "granite-4.2-8b": "Granite-4.2-8B", "ministral-3-8b": "Ministral-3-8B",
    "olmo-3-7b": "OLMo-3-7B", "nemotron-nano-9b-v2": "Nemotron-Nano-9B-v2", "gpt-oss-20b": "gpt-oss-20b",
    "phi-4": "Phi-4", "gemma-3-12b": "Gemma-3-12B", "glm-4.6v-flash": "GLM-4.6V-Flash",
    "llama-3.1-8b": "Llama-3.1-8B", "qwen3-8b": "Qwen3-8B",
}


def slug(m: str) -> str:
    return m.replace(".", "-")


def t(x, y, s, size=12, anchor="start", fill=INK2, weight=400, cls="", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" '
            f'font-weight="{weight}" class="{cls}" {extra}>{escape(str(s))}</text>')


def svg(w, h, body, title, desc, cls="chart"):
    return (f'<svg class="{cls}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="t d" '
            f'xmlns="http://www.w3.org/2000/svg"><title>{escape(title)}</title><desc>{escape(desc)}</desc>'
            f"{body}</svg>")


def hbar(x, y, w, h, fill, tip, round_end=True):
    """Horizontal bar from the baseline x; 4px rounded data end, square at the baseline."""
    if w <= 0:
        return ""
    r = min(4, h / 2, w) if round_end else 0
    path = (f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r:.1f} a{r},{r} 0 0 1 -{r},{r} "
            f"h-{w - r:.1f} z") if r else f"M{x:.1f},{y:.1f} h{w:.1f} v{h:.1f} h-{w:.1f} z"
    return f'<path d="{path}" fill="{fill}"><title>{escape(tip)}</title></path>'


def dot(x, y, fill, tip, r=5):
    return (f'<g class="mark"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 2}" fill="{SURF}"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}"><title>{escape(tip)}</title></circle>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 7}" fill="transparent"><title>{escape(tip)}</title>'
            "</circle></g>")


def legend(items, x, y, gap=22):
    out, cx = [], x
    for color, label in items:
        out.append(f'<rect x="{cx:.1f}" y="{y - 9:.1f}" width="10" height="10" rx="2" fill="{color}"/>')
        out.append(t(cx + 15, y, label, 12, fill=INK2))
        cx += 15 + 6.6 * len(label) + gap
    return "".join(out)


def pct(r):
    return f"{100 * r:.1f}%"


def acc(run, s):
    return run["setups"][s]["summary"]["accuracy"]


def cw(run, s):
    return run["setups"][s]["summary"]["confident_wrong"]


# -- figure: accuracy vs confident-wrong (the main chart) -----------------------------------------------------


# label placement: (x %, y %, anchor setup, text-anchor). Layout only; values come from the data.
LABELS = {
    "qwen3.5-9b": (0.3, 90.5, "C2", "start"), "granite-4.2-8b": (3.6, 90.5, "C3", "start"),
    "glm-4.6v-flash": (7.3, 90.5, "C3", "start"), "gpt-oss-20b": (11.6, 90.5, "C3", "start"),
    "ministral-3-8b": (8.9, 66.4, "C2", "start"), "gemma-3-12b": (13.9, 66.6, "C2", "start"),
    "llama-3.1-8b": (9.8, 55.6, "C1", "end"), "phi-4": (16.9, 53.6, "C2", "end"),
    "nemotron-nano-9b-v2": (6.6, 50.0, "C3", "end"), "olmo-3-7b": (7.6, 21.0, "C1", "start"),
}


def frontier(d):
    W, H, L, R, T, B = 760, 500, 64, 24, 56, 54
    xmax, ymin, ymax = 18, 10, 93
    X = lambda v: L + (v / xmax) * (W - L - R)  # noqa: E731
    Y = lambda v: T + (1 - (v - ymin) / (ymax - ymin)) * (H - T - B)  # noqa: E731
    b = []
    for v in range(0, xmax + 1, 3):
        b.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T}" y2="{H - B}" stroke="{GRID}"/>')
        b.append(t(X(v), H - B + 18, f"{v}%", 11, "middle", MUTED, cls="num"))
    for v in range(ymin, 91, 10):
        b.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{GRID}"/>')
        b.append(t(L - 8, Y(v) + 4, f"{v}%", 11, "end", MUTED, cls="num"))
    b.append(t((L + W - R) / 2, H - 12, "Confident-wrong rate: wrong answers that pass every automatic check (of 1,000)",
               12, "middle", INK2))
    b.append(t(14, (T + H - B) / 2, "Accuracy with checkable evidence (of 875)", 12, "middle", INK2,
               extra=f'transform="rotate(-90 14 {(T + H - B) / 2})"'))
    pt = lambda run, s: (100 * cw(run, s)["rate"], 100 * acc(run, s)["rate"])  # noqa: E731
    for m in d["ten"]:  # spokes from the plain setup to each other setup
        run = d["runs"][m]
        x1, y1 = pt(run, "C1")
        for s in ("C2", "C3"):
            if s in run["setups"]:
                x2, y2 = pt(run, s)
                b.append(f'<line x1="{X(x1):.1f}" y1="{Y(y1):.1f}" x2="{X(x2):.1f}" y2="{Y(y2):.1f}" '
                         f'stroke="{SETUP[s]}" stroke-opacity="0.45" stroke-width="1.5"/>')
    for m in d["ten"]:  # labels with leader lines
        run = d["runs"][m]
        lx, ly, s, an = LABELS[m]
        ax, ay = pt(run, s)
        tx, ty = X(lx), Y(ly)
        ex = tx + 3.3 * len(NAMES[m]) if ly > 85 else tx
        b.append(f'<line x1="{X(ax):.1f}" y1="{Y(ay):.1f}" x2="{ex:.1f}" y2="{ty + (4 if ly > 85 else -4):.1f}" '
                 f'stroke="{AXIS}" stroke-width="1"/>' if abs(Y(ay) - ty) > 14 or abs(X(ax) - tx) > 14 else "")
        b.append(t(tx + (0 if ly > 85 else (6 if an == "start" else -6)), ty + (-2 if ly > 85 else 4), NAMES[m],
                   12, an, INK, 500))
    for m in d["ten"]:
        run = d["runs"][m]
        for s in ("C1", "C2", "C3"):
            if s in run["setups"]:
                x, y = pt(run, s)
                b.append(dot(X(x), Y(y), SETUP[s], f"{NAMES[m]}, {SETUP_NAME[s]}: accuracy {y:.1f}%, "
                                                    f"confident-wrong {x:.1f}%"))
    b.append(legend([(SETUP[s], SETUP_NAME[s]) for s in SETUP], L, 20))
    b.append(t(W - R, 20, "better: up and to the left", 11.5, "end", MUTED))
    return svg(W, H, "".join(b), "Accuracy against confident-wrong rate, per model and setup",
               "Each model's plain setup is joined to its check-and-retry and thinking setups. Up and to the left "
               "is better: more answers right with checkable evidence and fewer wrong answers that pass every check.")


# -- figure: leaderboard with intervals --------------------------------------------------------------------


def leaderboard(d, models=None, metric="accuracy"):
    models = models or sorted(d["ten"], key=lambda m: -acc(d["runs"][m], "C1")["rate"])
    rows = len(models)
    W, L, R, T, rowh = 760, 170, 30, 44, 30
    H = T + rows * rowh + 40
    lo, hi = (0, 100) if metric == "accuracy" else (0, 20)
    X = lambda v: L + (v - lo) / (hi - lo) * (W - L - R)  # noqa: E731
    b = []
    for v in range(lo, hi + 1, 10 if metric == "accuracy" else 5):
        b.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T - 8}" y2="{T + rows * rowh}" stroke="{GRID}"/>')
        b.append(t(X(v), T + rows * rowh + 18, f"{v}%", 11, "middle", MUTED, cls="num"))
    for i, m in enumerate(models):
        run, y = d["runs"][m], T + i * rowh + rowh / 2
        b.append(t(L - 12, y + 4, NAMES[m], 13, "end", INK, 500))
        for j, s in enumerate(("C1", "C2", "C3")):
            if s not in run["setups"]:
                continue
            r = run["setups"][s]["summary"][metric if metric == "accuracy" else "confident_wrong"]
            yy = y + (j - 1) * 7
            a, z = 100 * r["ci95"][0], 100 * r["ci95"][1]
            b.append(f'<line x1="{X(a):.1f}" x2="{X(z):.1f}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{SETUP[s]}" '
                     f'stroke-width="2" stroke-linecap="round"/>')
            b.append(dot(X(100 * r["rate"]), yy, SETUP[s], f"{NAMES[m]}, {SETUP_NAME[s]}: {pct(r['rate'])} "
                                                            f"(95% CI {a:.1f}–{z:.1f}%), {r['k']} of {r['n']}", 4))
    b.append(legend([(SETUP[s], SETUP_NAME[s]) for s in SETUP], L, 20))
    what = "Accuracy" if metric == "accuracy" else "Confident-wrong rate"
    return svg(W, H, "".join(b), f"{what} per model and setup, with 95% Wilson intervals",
               f"{what} for each model in each of its setups; the line is the 95% interval.")


# -- figure: where the answers go ---------------------------------------------------------------------------


def outcome_bars(d, setup="C1", models=None, per_model_setups=False, run=None):
    """Stacked bars over the 875 answerable questions. Either one bar per model (one setup) or, for a model
    page, one bar per setup of that model."""
    if per_model_setups:
        items = [(SETUP_NAME[s] + f" ({s})", run["setups"][s]["summary"]) for s in ("C1", "C2", "C3")
                 if s in run["setups"]]
    else:
        models = models or sorted(d["ten"], key=lambda m: -acc(d["runs"][m], setup)["rate"])
        items = [(NAMES[m], d["runs"][m]["setups"][setup]["summary"]) for m in models if setup in
                 d["runs"][m]["setups"]]
    W, L, R, T, rowh, bh = 760, 170, 24, 56, 30, 18
    H = T + len(items) * rowh + 30
    X = lambda v: L + v / 875 * (W - L - R)  # noqa: E731
    b = []
    for v in (0, 0.25, 0.5, 0.75, 1):
        b.append(f'<line x1="{X(875 * v):.1f}" x2="{X(875 * v):.1f}" y1="{T - 6}" y2="{T + len(items) * rowh}" '
                 f'stroke="{GRID}"/>')
        b.append(t(X(875 * v), T + len(items) * rowh + 16, f"{int(100 * v)}%", 11, "middle", MUTED, cls="num"))
    for i, (name, summ) in enumerate(items):
        y = T + i * rowh + (rowh - bh) / 2
        b.append(t(L - 12, y + bh / 2 + 4, name, 13, "end", INK, 500))
        x = L
        oc = dict(summ["outcomes"])
        segs = [(o, oc.get(o, 0)) for o in OUT_ORDER if oc.get(o, 0)]
        for j, (o, k) in enumerate(segs):
            w = X(k) - L - (2 if j < len(segs) - 1 else 0)
            tip = f"{name}: {d['outcome_label'][o]} {k} of 875 ({100 * k / 875:.1f}%)"
            b.append(hbar(x, y, max(w, 0.5), bh, OUT[o], tip, round_end=(j == len(segs) - 1)))
            if w > 34 and o in ("correct", "confident_wrong"):
                b.append(t(x + 6, y + bh / 2 + 4, f"{100 * k / 875:.0f}%", 11, fill="#FFFFFF", weight=500, cls="num"))
            x += X(k) - L
    b.append(legend([(OUT[o], lab) for o, lab in [("correct", "Correct"), ("unverifiable_right", "Right, bad evidence"),
                                                  ("missed", "Missed"), ("invalid", "Unparseable"), ("caught_wrong", "Wrong, caught"),
                                                  ("confident_wrong", "Wrong, passed checks")]], 0, 20, 14))
    return svg(W, H, "".join(b), "Where the answers go (875 answerable questions)",
               "Each bar splits the answerable questions by outcome, from correct (left) through missed to wrong "
               "answers caught by the checker and wrong answers that passed every check (right).")


# -- figure: model x slice heatmap ---------------------------------------------------------------------------


def _seq(v):
    """Sequential indigo ramp, 0..1 -> light..dark (interpolated in sRGB between validated end steps)."""
    a, z = (0xEE, 0xF0, 0xFA), (0x1F, 0x2C, 0x73)
    c = [round(a[i] + (z[i] - a[i]) * v) for i in range(3)]
    return "#" + "".join(f"{v:02X}" for v in c)


def heatmap(d, setup="C1", models=None):
    models = models or sorted(d["ten"], key=lambda m: -acc(d["runs"][m], setup)["rate"])
    models = [m for m in models if setup in d["runs"][m]["setups"]]
    sl = list(d["slices"])
    W, L, T, cw_, ch = 760, 170, 60, 70, 26
    H = T + len(models) * ch + 16
    b = []
    for j, s in enumerate(sl):
        b.append(t(L + j * cw_ + cw_ / 2, T - 26, s, 12, "middle", INK, 600))
        b.append(t(L + j * cw_ + cw_ / 2, T - 10, ["Current", "Prior", "Qtr/YTD", "Notes", "Segments", "Prose",
                                                   "Units", "Absent"][j], 10.5, "middle", MUTED))
    for i, m in enumerate(models):
        by = d["runs"][m]["setups"][setup]["summary"]["by_slice"]
        y = T + i * ch
        b.append(t(L - 12, y + ch / 2 + 4, NAMES[m], 13, "end", INK, 500))
        for j, s in enumerate(sl):
            r = by[s]["rate"]
            v = max(0.0, min(1.0, (r - 0.1) / 0.9))
            fill = _seq(v)
            b.append(f'<rect x="{L + j * cw_ + 1:.1f}" y="{y + 1:.1f}" width="{cw_ - 2}" height="{ch - 2}" rx="3" '
                     f'fill="{fill}"><title>{escape(NAMES[m])}, {s} {escape(d["slices"][s])}: {pct(r)} '
                     f'({by[s]["k"]} of {by[s]["n"]})</title></rect>')
            b.append(t(L + j * cw_ + cw_ / 2, y + ch / 2 + 4, f"{100 * r:.0f}", 11, "middle",
                       "#FFFFFF" if v > 0.5 else INK, 500, cls="num"))
    return svg(W, H, "".join(b), f"Accuracy by kind of content ({SETUP_NAME[setup]})",
               "Rows are models, columns are the eight slices; darker is more accurate. S8 is the share of "
               "correct 'not found' answers.")


# -- figure: what kind of confident-wrong ---------------------------------------------------------------------


CW_CAT = [("scale_or_unit", "Scale or unit", "#B3302A"), ("wrong_period_or_column", "Wrong period or column",
                                                          "#E57C62"),
          ("wrong_item", "Wrong item", "#F1B9A6")]


def cw_mix(d, setup="C1", models=None):
    models = models or sorted(d["ten"], key=lambda m: cw(d["runs"][m], setup)["k"])
    W, L, R, T, rowh, bh = 760, 170, 40, 50, 28, 16
    H = T + len(models) * rowh + 28
    mx = max(cw(d["runs"][m], setup)["k"] for m in models)
    mx = int(math.ceil(mx / 25) * 25)
    X = lambda v: L + v / mx * (W - L - R)  # noqa: E731
    b = []
    for v in range(0, mx + 1, 25):
        b.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T - 6}" y2="{T + len(models) * rowh}" stroke="{GRID}"/>')
        b.append(t(X(v), T + len(models) * rowh + 16, str(v), 11, "middle", MUTED, cls="num"))
    for i, m in enumerate(models):
        y = T + i * rowh + (rowh - bh) / 2
        b.append(t(L - 12, y + bh / 2 + 4, NAMES[m], 13, "end", INK, 500))
        # categories of confident-wrong only: recount from the outcome-specific split stored per model
        split = d["cw_split"][f"{m}:{setup}"]
        segs = [(k, lab, col, split.get(k, 0)) for k, lab, col in CW_CAT if split.get(k, 0)]
        x = L
        for j, (_k, lab, col, n) in enumerate(segs):
            w = X(n) - L - (2 if j < len(segs) - 1 else 0)
            b.append(hbar(x, y, max(w, 0.5), bh, col, f"{NAMES[m]}: {lab} {n}", round_end=(j == len(segs) - 1)))
            x += X(n) - L
        b.append(t(x + 6, y + bh / 2 + 4, str(sum(n for *_, n in segs)), 11, fill=INK2, cls="num"))
    b.append(legend([(c, lab) for _, lab, c in CW_CAT], 0, 20, 16))
    return svg(W, H, "".join(b), "What the wrong-but-passing answers got wrong",
               "For each model, its confident-wrong answers split by error type.")


# -- figure: effect of retry and thinking ----------------------------------------------------------------------


def effects(d):
    models = [m for m in d["ten"]]
    models.sort(key=lambda m: -acc(d["runs"][m], "C1")["rate"])
    W, L, T, rowh = 760, 170, 64, 26
    H = T + len(models) * rowh + 40
    panels = [("Accuracy change (points)", "acc", -15, 15), ("Confident-wrong change (per 1,000)", "cw", -60, 30)]
    pw = (W - L - 60) / 2
    b = []
    tests = {(x["model"], x["a"], x["b"]): x for x in d["setup_tests"]}
    for p, (title, key, lo, hi) in enumerate(panels):
        x0 = L + p * (pw + 44)
        X = lambda v, x0=x0, lo=lo, hi=hi: x0 + (v - lo) / (hi - lo) * pw  # noqa: E731
        b.append(t(x0 + pw / 2, 40, title, 12, "middle", INK, 600))
        step = 5 if key == "acc" else 20
        for v in range(lo, hi + 1, step):
            b.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T - 8}" y2="{T + len(models) * rowh}" '
                     f'stroke="{AXIS if v == 0 else GRID}"/>')
            b.append(t(X(v), T + len(models) * rowh + 16, f"{v:+d}" if v else "0", 10.5, "middle", MUTED, cls="num"))
        for i, m in enumerate(models):
            run, y = d["runs"][m], T + i * rowh + rowh / 2
            if p == 0:
                b.append(t(L - 12, y + 4, NAMES[m], 13, "end", INK, 500))
            for s in ("C2", "C3"):
                if s not in run["setups"]:
                    continue
                if key == "acc":
                    v = 100 * (acc(run, s)["rate"] - acc(run, "C1")["rate"])
                else:
                    v = cw(run, s)["k"] - cw(run, "C1")["k"]
                tst = tests[(m, "C1", s)][key]
                sig = "significant" if tst["sig"] else "not significant"
                tip = f"{NAMES[m]}, {SETUP_NAME[s]} vs plain: {v:+.1f} ({sig}, Holm p = {tst['p_holm']:.3g})"
                v = max(lo, min(hi, v))
                if tst["sig"]:
                    b.append(dot(X(v), y, SETUP[s], tip, 5))
                else:
                    b.append(f'<g class="mark"><circle cx="{X(v):.1f}" cy="{y:.1f}" r="4.5" fill="{SURF}" '
                             f'stroke="{SETUP[s]}" stroke-width="2"><title>{escape(tip)}</title></circle></g>')
    b.append(legend([(SETUP["C2"], "Check + retry vs plain"), (SETUP["C3"], "Thinking vs plain")], L, 18))
    b.append(t(W - 4, 18, "hollow = not significant (Holm)", 11, "end", MUTED))
    return svg(W, H, "".join(b), "What check + retry and thinking change, compared with the plain setup",
               "Left: change in accuracy. Right: change in the number of confident-wrong answers. Filled dots are "
               "significant after Holm correction; hollow dots are not.")


# -- figure: cost of thinking ---------------------------------------------------------------------------------


def cost(d):
    models = [m for m in d["ten"] + d["supplementary"] if "C3" in d["runs"][m]["setups"]]
    W, H, L, R, T, B = 760, 400, 64, 150, 40, 54
    X = lambda v: L + (math.log10(v) - 1.5) / (4 - 1.5) * (W - L - R)  # noqa: E731
    Y = lambda v: T + (1 - (v - 40) / 50) * (H - T - B)  # noqa: E731
    b = []
    for v in (50, 100, 300, 1000, 3000, 10000):
        b.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T}" y2="{H - B}" stroke="{GRID}"/>')
        b.append(t(X(v), H - B + 18, f"{v:,}", 11, "middle", MUTED, cls="num"))
    for v in range(40, 91, 10):
        b.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{GRID}"/>')
        b.append(t(L - 8, Y(v) + 4, f"{v}%", 11, "end", MUTED, cls="num"))
    b.append(t((L + W - R) / 2, H - 12, "Generated tokens per answer (mean, log scale)", 12, "middle", INK2))
    for m in models:
        run = d["runs"][m]
        p1 = (run["setups"]["C1"]["tokens"]["mean"], 100 * acc(run, "C1")["rate"])
        p3 = (run["setups"]["C3"]["tokens"]["mean"], 100 * acc(run, "C3")["rate"])
        b.append(f'<line x1="{X(p1[0]):.1f}" y1="{Y(p1[1]):.1f}" x2="{X(p3[0]):.1f}" y2="{Y(p3[1]):.1f}" '
                 f'stroke="{AXIS}" stroke-width="1.5"/>')
        b.append(dot(X(p1[0]), Y(p1[1]), SETUP["C1"], f"{NAMES[m]}, plain: {p1[0]:.0f} tokens, {p1[1]:.1f}%", 4.5))
        b.append(dot(X(p3[0]), Y(p3[1]), SETUP["C3"], f"{NAMES[m]}, thinking: {p3[0]:.0f} tokens, {p3[1]:.1f}%",
                     4.5))
        dy = {"gpt-oss-20b": 14, "granite-4.2-8b": -6}.get(m, 4)
        b.append(t(X(p3[0]) + 10, Y(p3[1]) + dy, NAMES[m] + (" *" if m in d["supplementary"] else ""), 12, fill=INK,
                   weight=500))
    b.append(legend([(SETUP["C1"], "Plain"), (SETUP["C3"], "Thinking")], L, 20))
    return svg(W, H, "".join(b), "Thinking: accuracy against the tokens it costs",
               "For each model with a reasoning mode, the plain and thinking setups joined by a line: horizontal "
               "distance is the extra generation cost, vertical distance the accuracy gained or lost.")


# -- figure: significance matrix -----------------------------------------------------------------------------


def sig_matrix(d, key="C1:acc"):
    s, metric = key.split(":")
    models = sorted([m for m in d["ten"] if s in d["runs"][m]["setups"]],
                    key=lambda m: -acc(d["runs"][m], s)["rate"])
    n = len(models)
    cs, L, T = 34, 170, 150
    W, H = L + n * cs + 20, T + n * cs + 20
    tests = {}
    for x in d["model_tests"][key]:
        tests[(x["a"], x["b"])] = x
        tests[(x["b"], x["a"])] = {**x, "a_only": x["b_only"], "b_only": x["a_only"]}
    b = []
    for j, m in enumerate(models):
        cx = L + j * cs + cs / 2
        b.append(t(cx, T - 8, NAMES[m], 11.5, "start", INK, 500, extra=f'transform="rotate(-55 {cx} {T - 8})"'))
    for i, a in enumerate(models):
        y = T + i * cs
        b.append(t(L - 10, y + cs / 2 + 4, NAMES[a], 12, "end", INK, 500))
        for j, c in enumerate(models):
            x = L + j * cs
            if a == c:
                b.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cs - 2}" height="{cs - 2}" rx="3" fill="#F1F1EC"/>')
                continue
            tt = tests[(a, c)]
            better = tt["a_only"] > tt["b_only"]
            if tt["sig"]:
                fill = GOOD if better else "#E57C62"
            else:
                fill = "#E4E2DA"
            tip = (f"{NAMES[a]} vs {NAMES[c]}: right only for {NAMES[a]} {tt['a_only']}, only for {NAMES[c]} "
                   f"{tt['b_only']}; Holm p = {tt['p_holm']:.3g} ({'significant' if tt['sig'] else 'not significant'})")
            b.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cs - 2}" height="{cs - 2}" rx="3" fill="{fill}">'
                     f"<title>{escape(tip)}</title></rect>")
    b.append(legend([(GOOD, "Row better"), ("#E57C62", "Row worse"), ("#E4E2DA", "No significant difference")],
                    0, 18, 14))
    return svg(W, H, "".join(b), f"Which accuracy differences are real ({SETUP_NAME[s]})",
               "Paired exact McNemar tests on the same 875 questions, Holm-corrected over all 45 pairs.",
               cls="chart square")


# -- model page: slice profile ------------------------------------------------------------------------------


def slice_profile(d, run):
    sl = list(d["slices"])
    W, L, R, T, rowh = 760, 230, 30, 44, 26
    H = T + len(sl) * rowh + 34
    X = lambda v: L + v / 100 * (W - L - R)  # noqa: E731
    b = []
    for v in range(0, 101, 20):
        b.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T - 6}" y2="{T + len(sl) * rowh}" stroke="{GRID}"/>')
        b.append(t(X(v), T + len(sl) * rowh + 16, f"{v}%", 11, "middle", MUTED, cls="num"))
    for i, s in enumerate(sl):
        y = T + i * rowh + rowh / 2
        b.append(t(L - 12, y + 4, f"{s} · {d['slices'][s]}", 12.5, "end", INK, 500))
        for s2 in ("C1", "C2", "C3"):
            if s2 in run["setups"]:
                r = run["setups"][s2]["summary"]["by_slice"][s]
                b.append(dot(X(100 * r["rate"]), y, SETUP[s2], f"{s} {d['slices'][s]}, {SETUP_NAME[s2]}: "
                                                              f"{pct(r['rate'])} ({r['k']} of {r['n']})", 4.5))
    b.append(legend([(SETUP[s], SETUP_NAME[s]) for s in SETUP if s in run["setups"]], L, 20))
    return svg(W, H, "".join(b), "Accuracy by kind of content, per setup",
               "One row per slice; dots are this model's setups. S8 shows correct 'not found' answers.")
