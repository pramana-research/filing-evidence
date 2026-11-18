"""Every number in the paper and the model pages, computed from the stored replies (results/main/*/C*/answers.jsonl).

Pure functions plus one loader. Grades are taken as stored (they are the checker's output; `runner.py --regrade`
reproduces them). Statistics follow PROTOCOL §10: Wilson 95% intervals; paired exact McNemar tests; Holm
correction within each family of comparisons, alpha 0.05.
"""

from __future__ import annotations

import json
import math
import re
import sys
from itertools import combinations
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
import checker  # noqa: E402

SETUPS = ("C1", "C2", "C3")
TEN = [  # the pre-registered comparison (PROTOCOL §2), in the protocol's order
    "qwen3.5-9b", "granite-4.2-8b", "ministral-3-8b", "olmo-3-7b", "nemotron-nano-9b-v2",
    "gpt-oss-20b", "phi-4", "gemma-3-12b", "glm-4.6v-flash", "llama-3.1-8b",
]
SUPPLEMENTARY = ["qwen3-8b"]  # §12: reported separately, never ranked with the ten
SLICES = {
    "S1": "Main statements, current period",
    "S2": "Main statements, prior period",
    "S3": "10-Q quarter vs year-to-date",
    "S4": "Notes tables",
    "S5": "Segments",
    "S6": "Numbers in prose",
    "S7": "Units and per-share",
    "S8": "Not in the provided pages",
}
OUTCOME_LABEL = {
    "correct": "Correct",
    "unverifiable_right": "Right value, unusable evidence",
    "missed": "Missed (said not found)",
    "caught_wrong": "Wrong, caught by the checker",
    "confident_wrong": "Wrong, passed every check",
    "invalid": "Unparseable",
    "abstained_correctly": "Correctly said not found",
    "invented": "Invented an answer",
}
CATEGORY_LABEL = {
    "wrong_line_quoted": "Wrong line quoted",
    "wrong_page_cited": "Wrong page cited",
    "span_not_verbatim": "Quote not verbatim",
    "scale_or_unit": "Scale or unit",
    "wrong_period_or_column": "Wrong period or column",
    "wrong_item": "Wrong item",
    "invented_on_s8": "Invented (not-in-pages question)",
    "missed": "Missed",
    "invalid_format": "Invalid format",
}


# -- loading -------------------------------------------------------------------------------------------------


def load_questions() -> dict[str, dict]:
    return {q["id"]: q for q in map(json.loads, (ROOT / "dataset" / "questions.jsonl").open())}


def load_pages() -> dict[str, dict]:
    return {p["id"]: p for p in map(json.loads, (ROOT / "dataset" / "pages.jsonl").open())}


def load_rows(model: str, setup: str) -> list[dict] | None:
    p = ROOT / "results" / "main" / model / setup / "answers.jsonl"
    if not p.exists():
        return None
    return sorted(map(json.loads, p.open()), key=lambda r: r["id"])


def profiles() -> dict:
    return yaml.safe_load((ROOT / "models.yaml").read_text())["models"]


def model_meta() -> dict:
    return json.loads((Path(__file__).parent / "model_meta.json").read_text())["models"]


# -- statistics ----------------------------------------------------------------------------------------------


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for b and c discordant pairs (binomial test, p = 0.5)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def holm(pvals: dict, alpha: float = 0.05) -> dict:
    """Holm step-down: {key: (p, p_adjusted, significant)}."""
    order = sorted(pvals, key=lambda k: pvals[k])
    m, running, out = len(order), 0.0, {}
    for i, k in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvals[k]))
        out[k] = (pvals[k], running, running < alpha)
    return out


def paired(a: list[bool], b: list[bool]) -> dict:
    """a, b: per-question success flags in the same question order."""
    b_only = sum(1 for x, y in zip(a, b, strict=True) if not x and y)
    a_only = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    return {"a_only": a_only, "b_only": b_only, "p": mcnemar_exact(a_only, b_only)}


# -- building blocks -----------------------------------------------------------------------------------------


def correct_flags(rows: list[dict]) -> list[bool]:
    return [r["outcome"] == "correct" for r in rows if r["slice"] != "S8"]


def cw_flags(rows: list[dict]) -> list[bool]:
    return [r["outcome"] == "confident_wrong" for r in rows]


def run_meta(model: str, setup: str) -> dict:
    return json.loads((ROOT / "results" / "main" / model / setup / "run.json").read_text())


def wall_minutes(meta: dict) -> float:
    from datetime import datetime

    a, b = (datetime.fromisoformat(meta[k]) for k in ("started", "finished"))
    return (b - a).total_seconds() / 60


def tokens(rows: list[dict]) -> dict:
    """Completion tokens per question over all attempts (C2 includes the retry), and reasoning share."""
    toks = [r["completion_tokens"] for r in rows]
    trunc = sum(bool(r.get("truncated")) for r in rows)
    return {"mean": sum(toks) / len(toks), "median": sorted(toks)[len(toks) // 2],
            "p95": checker._pct(toks, 0.95), "truncated": trunc}


def example(r: dict, q: dict) -> dict:
    a = r.get("answer") or {}
    g = q["gold"]
    ev = g.get("evidence") or [{}]
    return {
        "id": r["id"], "ticker": q["ticker"], "company": q.get("company"), "form": q["form"],
        "slice": q["slice"], "question": q["question"], "outcome": r["outcome"], "category": r.get("category"),
        "answer_value": a.get("value"), "answer_scale": a.get("scale"), "answer_page": a.get("page"),
        "answer_span": a.get("span"), "answer_status": a.get("status"),
        "gold_display": g.get("display"), "gold_scale": g.get("scale"), "gold_unit": g.get("unit"),
        "gold_line": ev[0].get("line"), "gold_page": ev[0].get("page"), "gold_status": g["status"],
        "failed_check": r.get("failed_check"),
    }


def pick(rows: list[dict], qs: dict, outcome: str, n: int, category: str | None = None, seed: int = 0,
         exclude: set | frozenset = frozenset()) -> list:
    """Deterministic examples: evenly spaced over question ids, so they span companies and slices. Questions in
    `exclude` (those without an on-page units statement) are never shown as examples."""
    pool = [r for r in rows if r["outcome"] == outcome and r["id"] not in exclude
            and (category is None or r.get("category") == category)]
    if not pool:
        return []
    step = max(1, len(pool) // n)
    return [example(r, qs[r["id"]]) for r in pool[seed::step][:n]]


# -- the whole report --------------------------------------------------------------------------------------


UNIT_WORD = {3: "thousand", 6: "million", 9: "billion"}


def no_units_header(qs: dict, pages: dict) -> list[str]:
    """Answerable questions whose evidence page states no units (found after the results: the filer states them once
    on an earlier page): no plural scale word ("millions") on the page and no scale written with the figure itself
    ("$5 million"). A singular mention in unrelated prose ("$253 million of credits") is not a units statement for a
    table. Used only for the sensitivity analysis; the frozen dataset is unchanged."""
    out = []
    for q in qs.values():
        g = q["gold"]
        if g["status"] == "found" and g.get("scale") in UNIT_WORD and g["unit"] in ("USD", "shares"):
            word, ev = UNIT_WORD[g["scale"]], g["evidence"][0]
            if word + "s" not in pages[ev["page"]]["text"].lower() and not re.search(rf"\d\s*{word}", ev["line"].lower()):
                out.append(q["id"])
    return sorted(out)


def quotes_whole_line(r: dict, q: dict, pages: dict) -> bool:
    """Whether a passing answer's quote is one complete line of the cited page (the checker requires less: any
    verbatim run of text on that page, whitespace normalised)."""
    labels = dict(zip(q["page_labels"], q["pages"], strict=True))
    text = pages[labels[checker.to_page(r["answer"]["page"])]]["text"]
    return checker.norm_ws(str(r["answer"]["span"])) in {checker.norm_ws(x) for x in text.split("\n")}


def robustness(qs: dict, pages: dict, rows_by: dict, noheader: set) -> dict:
    """Plain-setup figures that qualify the headline definitions, over the ten ranked models."""
    c1 = {m: rows_by[(m, "C1")] for m in TEN}
    correct = [(r, qs[r["id"]]) for rows in c1.values() for r in rows if r["outcome"] == "correct"]
    invented = {m: sum(r["outcome"] == "invented" and r["failed_check"] is None for r in rows) for m, rows in c1.items()}
    kept = [r for rows in c1.values() for r in rows if r["outcome"] == "confident_wrong" and r["id"] not in noheader]
    finished = {r["id"] for r in rows_by[("qwen3.5-9b", "C3")] if r["slice"] != "S8" and not r.get("truncated")}
    plain = [r for r in c1["qwen3.5-9b"] if r["id"] in finished]
    return {
        "correct": len(correct),
        "correct_partial_quote": sum(not quotes_whole_line(r, q, pages) for r, q in correct),
        "invented_passing": sum(invented.values()),
        "invented_passing_min": min(invented.values()), "invented_passing_max": max(invented.values()),
        "scale_share_without_noheader": sum(r["category"] == "scale_or_unit" for r in kept) / len(kept),
        "q35_plain_on_finished": checker._rate(sum(r["outcome"] == "correct" for r in plain), len(plain)),
    }


def compute() -> dict:
    qs = load_questions()
    pages = load_pages()
    noheader = set(no_units_header(qs, pages))
    prof, meta = profiles(), model_meta()
    models = TEN + SUPPLEMENTARY
    runs: dict[str, dict] = {}
    rows_by: dict[tuple[str, str], list[dict]] = {}
    for m in models:
        runs[m] = {"profile": m, "repo": prof[m]["repo"], "company": prof[m]["company"],
                   "precision": prof[m]["precision"], "has_c3": prof[m]["request"].get("C3") is not None,
                   "meta": meta[m], "supplementary": m in SUPPLEMENTARY, "setups": {}}
        for s in SETUPS:
            rows = load_rows(m, s)
            if rows is None:
                continue
            assert len(rows) == 1000, (m, s, len(rows))
            rows_by[(m, s)] = rows
            rm = run_meta(m, s)
            summ = checker.summarize(rows)
            rec = json.loads((Path(__file__).parent / "model_meta.json").read_text())["revision_reconstructed"]
            runs[m]["revision"] = rm["revision"] or rec[m]
            runs[m]["revision_reconstructed"] = rm["revision"] is None
            runs[m]["serve_command"] = rm["serve_command"]
            ans = [r for r in rows if r["slice"] != "S8" and r["id"] not in noheader]
            trunc = [r for r in rows if r.get("truncated")]
            runs[m]["setups"][s] = {
                "summary": summ, "tokens": tokens(rows), "wall_minutes": wall_minutes(rm),
                "acc_without_noheader": checker._rate(sum(r["outcome"] == "correct" for r in ans), len(ans)),
                "truncated_outcomes": {o: sum(r["outcome"] == o for r in trunc) for o in checker.OUTCOMES},
                "acc_untruncated": checker._rate(
                    sum(r["outcome"] == "correct" for r in rows if r["slice"] != "S8" and not r.get("truncated")),
                    sum(1 for r in rows if r["slice"] != "S8" and not r.get("truncated"))),
                "request_extra": rm.get("request_extra"), "system": rm.get("system"),
                "max_tokens": rm["max_tokens"],
            }

    # within-model setup comparisons (accuracy on 875; confident-wrong on 1,000), Holm across the whole family
    fam_acc, fam_cw = {}, {}
    for m in models:
        have = [s for s in SETUPS if (m, s) in rows_by]
        for a, b in combinations(have, 2):
            ra, rb = rows_by[(m, a)], rows_by[(m, b)]
            fam_acc[(m, a, b)] = paired(correct_flags(ra), correct_flags(rb))
            fam_cw[(m, a, b)] = paired(cw_flags(ra), cw_flags(rb))
    h_acc = holm({k: v["p"] for k, v in fam_acc.items()})
    h_cw = holm({k: v["p"] for k, v in fam_cw.items()})
    setup_tests = [
        {"model": m, "a": a, "b": b, "acc": {**fam_acc[(m, a, b)], "p_holm": h_acc[(m, a, b)][1],
                                             "sig": h_acc[(m, a, b)][2]},
         "cw": {**fam_cw[(m, a, b)], "p_holm": h_cw[(m, a, b)][1], "sig": h_cw[(m, a, b)][2]}}
        for (m, a, b) in fam_acc
    ]

    # between-model comparisons among the ten, per setup, Holm within each (setup, metric) family
    model_tests = {}
    for s in SETUPS:
        have = [m for m in TEN if (m, s) in rows_by]
        for metric, flags in (("acc", correct_flags), ("cw", cw_flags)):
            fam = {(a, b): paired(flags(rows_by[(a, s)]), flags(rows_by[(b, s)])) for a, b in combinations(have, 2)}
            h = holm({k: v["p"] for k, v in fam.items()})
            model_tests[f"{s}:{metric}"] = [
                {"a": a, "b": b, **fam[(a, b)], "p_holm": h[(a, b)][1], "sig": h[(a, b)][2]} for (a, b) in fam
            ]

    # retry anatomy (C2): what the retried questions became, per model
    retry = {}
    for m in models:
        if (m, "C2") not in rows_by:
            continue
        c1 = {r["id"]: r for r in rows_by[(m, "C1")]}
        moves: dict[str, int] = {}
        for r in rows_by[(m, "C2")]:
            if r.get("retried"):
                k = f"{c1[r['id']]['outcome']}->{r['outcome']}"
                moves[k] = moves.get(k, 0) + 1
        retry[m] = moves

    # S8 sub-kinds
    s8 = {}
    for (m, s), rows in rows_by.items():
        kinds: dict[str, list[int]] = {}
        for r in rows:
            if r["slice"] == "S8":
                k = qs[r["id"]].get("subtype") or "?"
                kinds.setdefault(k, [0, 0])
                kinds[k][0] += r["outcome"] == "abstained_correctly"
                kinds[k][1] += 1
        s8[f"{m}:{s}"] = kinds

    # examples per model (its best setup by accuracy)
    examples = {}
    for m in models:
        best = max(runs[m]["setups"], key=lambda s: runs[m]["setups"][s]["summary"]["accuracy"]["rate"])
        runs[m]["best_setup"] = best
        rows = rows_by[(m, best)]
        examples[m] = {
            "setup": best,
            "correct": pick(rows, qs, "correct", 2, seed=3, exclude=noheader),
            "confident_wrong": pick(rows, qs, "confident_wrong", 3, seed=1, exclude=noheader),
            "caught_wrong": pick(rows, qs, "caught_wrong", 1, seed=2, exclude=noheader),
            "unverifiable_right": pick(rows, qs, "unverifiable_right", 1, seed=2, exclude=noheader),
        }

    # pooled: confident-wrong categories across the ten (each model's C1 and best setup)
    pooled = {}
    for s in SETUPS:
        cats: dict[str, int] = {}
        for m in TEN:
            if (m, s) in rows_by:
                for r in rows_by[(m, s)]:
                    if r["outcome"] == "confident_wrong":
                        cats[r["category"]] = cats.get(r["category"], 0) + 1
        pooled[s] = cats

    # confident-wrong answers by error category, per model and setup
    cw_split = {f"{m}:{s}": {} for (m, s) in rows_by}
    for (m, s), rows in rows_by.items():
        for r in rows:
            if r["outcome"] == "confident_wrong":
                cw_split[f"{m}:{s}"][r["category"]] = cw_split[f"{m}:{s}"].get(r["category"], 0) + 1

    return {
        "cw_split": cw_split,
        "robustness": robustness(qs, pages, rows_by, noheader),
        "dataset": json.loads((ROOT / "dataset" / "stats.json").read_text()),
        "no_units_header": sorted(noheader),
        "frozen": json.loads((ROOT / "dataset" / "FROZEN.json").read_text()),
        "ten": TEN, "supplementary": SUPPLEMENTARY, "slices": SLICES,
        "outcome_label": OUTCOME_LABEL, "category_label": CATEGORY_LABEL,
        "runs": runs, "setup_tests": setup_tests, "model_tests": model_tests,
        "retry": retry, "s8": s8, "examples": examples, "pooled_cw_categories": pooled,
    }


if __name__ == "__main__":
    d = compute()
    out = Path(__file__).parent / "build" / "data.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(d, indent=1, default=str) + "\n")
    print(f"wrote {out}")
