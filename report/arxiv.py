"""The arXiv version of the paper: LaTeX source, vector figures, and the upload bundle.

    uv run python report/arxiv.py                 # -> paper/main.tex, paper/figures/*.pdf
    cd paper && pdflatex main && pdflatex main     # or: tectonic main.tex   (no BibTeX: references are inline)
    uv run python report/arxiv.py --bundle        # -> paper/arxiv-source.tar.gz (main.tex + figures)

Every number comes from stats.compute() and build.headline(), as on the website; the text is in
report/latex/main.tex.j2. Figures are the website's SVG charts and diagrams, printed to tightly cropped vector PDFs
by headless Chrome (fonts embedded).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402
import charts  # noqa: E402
import stats  # noqa: E402

PAPER = ROOT / "paper"
FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&"
         "family=JetBrains+Mono:wght@400;500&display=swap")


def chrome() -> str:
    for c in ("google-chrome", "chromium", "chromium-browser"):
        if p := shutil.which(c):
            return p
    sys.exit("headless Chrome is needed to print the figures")


def svg_to_pdf(svg: str, out: Path) -> None:
    """One SVG -> one PDF page of exactly the SVG's size (vector, fonts embedded)."""
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    w, h = float(m.group(1)), float(m.group(2))
    svg = svg.replace("<svg ", f'<svg width="{w}" height="{h}" ', 1)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><link href="{FONTS}" rel="stylesheet">
<style>@page {{ size: {w}px {h}px; margin: 0 }} html, body {{ margin: 0; background: #fff }}
svg {{ display: block; font-family: Inter, sans-serif }} svg .num {{ font-family: 'JetBrains Mono', monospace }}
</style></head><body>{svg}</body></html>"""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "fig.html"
        src.write_text(html)
        subprocess.run([chrome(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        "--virtual-time-budget=6000", f"--print-to-pdf={out}", src.as_uri()],
                       check=True, capture_output=True)


def tex_escape(s) -> str:
    """Plain text -> LaTeX (for question wording, quoted lines, model names)."""
    s = str(s)
    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
           "“": "``", "”": "''", "’": "'", "‘": "`", "–": "--", "—": "---", "…": r"\ldots{}",
           "≠": r"$\neq$", "→": r"$\rightarrow$", "×": r"$\times$", "§": r"\S{}", "✓": r"\checkmark{}"}
    return "".join(rep.get(c, c) for c in s)


def figures(d: dict, H: dict) -> list[str]:
    """Write paper/figures/*.pdf; return their names."""
    env = Environment(loader=FileSystemLoader(HERE / "templates"))
    dg = env.get_template("diagrams.html.j2").module
    figs = {
        "pipeline": str(dg.pipeline()), "checker": str(dg.checker()), "setups": str(dg.setups()),
        "frontier": charts.frontier(d),
        "significance": charts.sig_matrix(d, "C1:acc"), "outcomes": charts.outcome_bars(d, "C1"),
        "slices": charts.heatmap(d, "C1"), "cw-mix": charts.cw_mix(d, "C1"), "effects": charts.effects(d),
        "cost": charts.cost(d), "leaderboard-cw": charts.leaderboard(d, metric="confident_wrong"),
    }
    (PAPER / "figures").mkdir(parents=True, exist_ok=True)
    for name, svg in figs.items():
        svg_to_pdf(svg, PAPER / "figures" / f"{name}.pdf")
    return list(figs)


def render() -> None:
    d = stats.compute()
    qs, pages = stats.load_questions(), stats.load_pages()
    H = build.headline(d)
    names = figures(d, H)
    env = Environment(loader=FileSystemLoader(HERE / "latex"), undefined=StrictUndefined,
                      block_start_string="<%", block_end_string="%>", variable_start_string="<<",
                      variable_end_string=">>", comment_start_string="<#", comment_end_string="#>",
                      trim_blocks=True, lstrip_blocks=True, autoescape=False)
    env.filters.update(
        e=tex_escape, name=lambda m: tex_escape(charts.NAMES[m]), setup=lambda s: charts.SETUP_NAME[s],
        pct=lambda r, nd=1: f"{100 * r:.{nd}f}\\%", ci=lambda r: f"{100 * r['ci95'][0]:.1f}--{100 * r['ci95'][1]:.1f}",
        thou=lambda n: f"{n:,}".replace(",", "{,}"), num=lambda x, nd=1: f"{x:.{nd}f}",
        lcfirst=lambda x: x[:1].lower() + x[1:] if x[:2] != "10" else x,
    )
    ex = build.annotated(d, qs, pages)
    tex = env.get_template("main.tex.j2").render(
        d=d, H=H, ex=ex, figs=names, VERSION=build.VERSION, GITHUB=build.GITHUB, HF=build.HF,
        AUTHOR_EMAIL=os.environ.get("PAPER_AUTHOR_EMAIL", ""),
        LICENCE={"apache-2.0": "Apache 2.0", "mit": "MIT", "gemma": "Gemma Terms", "llama3.1": "Llama 3.1",
                 "nvidia-open-model-license": "NVIDIA Open Model"},
    )
    (PAPER / "main.tex").write_text(tex)
    print(f"wrote {PAPER / 'main.tex'} and {len(names)} figures")


def bundle() -> None:
    """The upload for arXiv: main.tex and the figures (references are inline, so no .bbl is needed)."""
    out = PAPER / "arxiv-source.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        tar.add(PAPER / "main.tex", arcname="main.tex")
        for f in sorted((PAPER / "figures").glob("*.pdf")):
            tar.add(f, arcname=f"figures/{f.name}")
    print(f"wrote {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", action="store_true", help="only pack paper/ into arxiv-source.tar.gz")
    a = ap.parse_args()
    bundle() if a.bundle else render()
