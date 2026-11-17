"""Build the research pages for pramana-research.com from the stored results.

    uv run python report/build.py --out ../pramana-research-landing      # writes research/** into the site repo
    bash report/pdf.sh ../pramana-research-landing                         # then the PDFs (headless Chrome)

Every number on the pages comes from stats.compute(); the prose is in the templates (report/templates/).
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import charts  # noqa: E402
import stats  # noqa: E402

VERSION = "1.0"
DATE = "17 November 2026"
SITE = "https://pramana-research.com"
GITHUB = "https://github.com/pramana-research/filing-evidence"
HF = "https://huggingface.co/datasets/pramana-research/filing-evidence"
BIBTEX = f"""@misc{{pramana2026filingevidence,
  title  = {{Show Your Work: Can Small Open Models Read SEC Filings with Evidence a Machine Can Check?}},
  author = {{{{Pramana Research}}}},
  year   = {{2026}},
  month  = {{nov}},
  note   = {{Filing-Evidence benchmark, version {VERSION}}},
  url    = {{{SITE}/research/filing-evidence}}
}}"""


def fmt_pct(r, nd=1):
    return f"{100 * r:.{nd}f}%"


def fmt_ci(r, nd=1):
    return f"{100 * r['ci95'][0]:.{nd}f}–{100 * r['ci95'][1]:.{nd}f}%"


def headline(d: dict) -> dict:
    """The figures the prose quotes, computed once here so the text and the charts can't disagree."""
    R, ten = d["runs"], d["ten"]
    acc = lambda m, s: R[m]["setups"][s]["summary"]["accuracy"]  # noqa: E731
    cw = lambda m, s: R[m]["setups"][s]["summary"]["confident_wrong"]  # noqa: E731
    with_c3 = [m for m in ten if "C3" in R[m]["setups"]]
    tests = {(t["model"], t["a"], t["b"]): t for t in d["setup_tests"]}
    pooled = d["pooled_cw_categories"]["C1"]
    tot = sum(pooled.values())
    c1_sorted = sorted(ten, key=lambda m: -acc(m, "C1")["rate"])
    best_any = max(((m, s) for m in ten for s in R[m]["setups"]), key=lambda x: acc(*x)["rate"])
    safest = min(((m, s) for m in ten for s in R[m]["setups"]), key=lambda x: cw(*x)["rate"])
    retry_gain = [100 * (acc(m, "C2")["rate"] - acc(m, "C1")["rate"]) for m in ten]
    retry_sig = [m for m in ten if tests[(m, "C1", "C2")]["acc"]["sig"]]
    retry_cw_up = [m for m in ten if tests[(m, "C1", "C2")]["cw"]["sig"]]
    think_gain = {m: 100 * (acc(m, "C3")["rate"] - acc(m, "C1")["rate"]) for m in with_c3}
    think_cw = {m: (cw(m, "C1")["k"], cw(m, "C3")["k"]) for m in with_c3}
    think_cw_sig = [m for m in with_c3 if tests[(m, "C1", "C3")]["cw"]["sig"]]
    tok_mult = {m: R[m]["setups"]["C3"]["tokens"]["mean"] / R[m]["setups"]["C1"]["tokens"]["mean"] for m in with_c3}
    slices_c1 = {}
    for m in ten:
        for k, v in R[m]["setups"]["C1"]["summary"]["by_slice"].items():
            a = slices_c1.setdefault(k, [0, 0])
            a[0] += v["k"]
            a[1] += v["n"]
    slices_c1 = {k: a / b for k, (a, b) in slices_c1.items()}
    sens = max(abs(R[m]["setups"][s]["acc_without_noheader"]["rate"] - acc(m, s)["rate"])
               for m in ten for s in R[m]["setups"])
    passp = [R[m]["setups"][s]["summary"]["checker_pass_precision"]["rate"] for m in ten for s in R[m]["setups"]]
    abst = [R[m]["setups"]["C1"]["summary"]["abstention_accuracy"]["rate"] for m in ten]
    q35 = R["qwen3.5-9b"]["setups"]["C3"]
    retry_moves = {m: d["retry"][m] for m in ten}
    caught_to_cw = {m: sum(v for k, v in mv.items() if k.endswith("->confident_wrong")) for m, mv in retry_moves.items()}
    retried = {m: sum(mv.values()) for m, mv in retry_moves.items()}
    return {
        "c1_sorted": c1_sorted, "with_c3": with_c3, "best_any": best_any, "safest": safest,
        "acc_c1_top": acc(c1_sorted[0], "C1"), "acc_c1_bottom": acc(c1_sorted[-1], "C1"),
        "cw_share": {k: v / tot for k, v in pooled.items()}, "cw_total_c1": tot,
        "retry_gain_min": min(retry_gain), "retry_gain_max": max(retry_gain), "retry_sig": retry_sig,
        "retry_cw_up": retry_cw_up, "think_gain": think_gain, "think_cw": think_cw, "think_cw_sig": think_cw_sig,
        "tok_mult": tok_mult, "slices_c1": slices_c1, "sens_max": sens, "passp_min": min(passp),
        "passp_max": max(passp), "abst_min": min(abst), "abst_max": max(abst), "q35_c3": q35,
        "caught_to_cw": caught_to_cw, "retried": retried,
        "think_cw_all_down": all(c3 < c1 for c1, c3 in think_cw.values()),
        "retry_to": {m: {o: sum(v for k, v in mv.items() if k.endswith("->" + o)) for o in
                         ("correct", "confident_wrong", "missed")} | {"total": sum(mv.values())}
                     for m, mv in d["retry"].items()},
        "n_noheader": len(d["no_units_header"]),
    }


def page_excerpt(q: dict, pages: dict, around: int = 3) -> dict:
    """Lines of the evidence page around the gold line, for the annotated example."""
    ev = q["gold"]["evidence"][0]
    lines = pages[ev["page"]]["text"].split("\n")
    idx = next((i for i, x in enumerate(lines) if stats.checker.norm_ws(ev["line"]) in stats.checker.norm_ws(x)), 0)
    head = [x for x in lines[:6] if x.strip()][:2]
    lo, hi = max(0, idx - around), min(len(lines), idx + around + 1)
    label = dict(zip(q["pages"], q["page_labels"], strict=True))[ev["page"]]
    return {"head": head, "lines": lines[lo:hi], "gold_index": idx - lo, "page_label": label}


def annotated(d: dict, qs: dict, pages: dict) -> dict:
    """A real confident-wrong answer of the best model in the plain setup: the right line, the wrong column."""
    rows = stats.load_rows("qwen3.5-9b", "C1")
    pick = next(r for r in rows if r["outcome"] == "confident_wrong" and r["category"] == "wrong_period_or_column"
                and r["slice"] in ("S2", "S1", "S3"))
    q = qs[pick["id"]]
    others = {m: next(r for r in stats.load_rows(m, "C1") if r["id"] == pick["id"])["outcome"] for m in d["ten"]}
    row = stats.example(pick, q)
    return {"row": row, "excerpt": page_excerpt(q, pages), "reply": pick["attempts"][0]["content"],
            "others": others, "marked": mark_line(row["gold_line"], row["answer_value"], row["gold_display"])}


def mark_line(line: str, model_value, gold_display: str) -> str:
    """The evidence line with the model's figure and the gold figure highlighted (HTML-escaped)."""
    from html import escape

    mv = abs(stats.checker.to_number(model_value) or 0)
    gv = stats.checker.to_number(gold_display)
    out, last = [], 0
    for mt in re.finditer(r"\(?\d[\d,]*(?:\.\d+)?\)?", line):
        n = abs(stats.checker.to_number(mt.group()) or -1)
        style = ("color:#B3302A;font-weight:700;text-decoration:underline" if stats.checker.same(n, mv) else
                 "color:#2E3F9E;font-weight:700;text-decoration:underline" if stats.checker.same(n, abs(gv)) else "")
        out.append(escape(line[last:mt.start()]))
        out.append(f'<span style="{style}">{escape(mt.group())}</span>' if style else escape(mt.group()))
        last = mt.end()
    out.append(escape(line[last:]))
    return "".join(out)


def build(out: Path) -> None:
    d = stats.compute()
    qs, pages = stats.load_questions(), stats.load_pages()
    H = headline(d)
    env = Environment(loader=FileSystemLoader(HERE / "templates"), undefined=StrictUndefined, autoescape=True,
                      trim_blocks=True, lstrip_blocks=True)
    env.filters.update(pct=fmt_pct, ci=fmt_ci, name=lambda m: charts.NAMES[m], slug=charts.slug,
                       setup=lambda s: charts.SETUP_NAME[s], thou=lambda n: f"{n:,}",
                       lcfirst=lambda x: x[:1].lower() + x[1:] if x[:2] != "10" else x)
    env.globals["LICENCE"] = {"apache-2.0": "Apache 2.0", "mit": "MIT", "gemma": "Gemma Terms of Use",
                              "llama3.1": "Llama 3.1 Community", "nvidia-open-model-license": "NVIDIA Open Model"}
    env.globals["tag"] = {"correct": ("good", "Correct"), "confident_wrong": ("bad", "Confident-wrong"),
                          "caught_wrong": ("mid", "Caught wrong"), "missed": ("mid", "Missed"),
                          "unverifiable_right": ("mid", "Right value, unusable evidence")}
    common = {"d": d, "H": H, "NAMES": charts.NAMES, "SETUP_NAME": charts.SETUP_NAME, "VERSION": VERSION,
              "DATE": DATE, "SITE": SITE, "GITHUB": GITHUB, "HF": HF, "BIBTEX": BIBTEX}
    figs = {
        "frontier": charts.frontier(d), "leader": charts.leaderboard(d),
        "leader_cw": charts.leaderboard(d, metric="confident_wrong"), "outcomes": charts.outcome_bars(d, "C1"),
        "heatmap": charts.heatmap(d, "C1"), "cwmix": charts.cw_mix(d, "C1"), "effects": charts.effects(d),
        "cost": charts.cost(d), "sig": charts.sig_matrix(d, "C1:acc"),
    }
    base = out / "research"
    fe = base / "filing-evidence"
    fe.mkdir(parents=True, exist_ok=True)
    (base / "assets").mkdir(exist_ok=True)
    shutil.copy(HERE / "templates" / "research.css", base / "assets" / "research.css")

    (base / "index.html").write_text(env.get_template("index.html.j2").render(**common, here="index"))
    (fe / "index.html").write_text(env.get_template("paper.html.j2").render(
        **common, figs=figs, ex=annotated(d, qs, pages), here="paper"))
    for m in d["ten"] + d["supplementary"]:
        run = d["runs"][m]
        mf = {"outcomes": charts.outcome_bars(d, per_model_setups=True, run=run),
              "slices": charts.slice_profile(d, run)}
        (fe / f"{charts.slug(m)}.html").write_text(env.get_template("model.html.j2").render(
            **common, m=m, run=run, mf=mf, ex=d["examples"][m], here="model"))
    print(f"wrote {base}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True, help="the pramana-research-landing checkout")
    build(ap.parse_args().out)
