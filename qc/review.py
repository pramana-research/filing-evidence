"""Hand-check support (PROTOCOL.md §11): draw the stratified sample and print what a reviewer
needs.

    python qc/review.py sample 2      # -> qc/handcheck_sample_v2.json
    python qc/review.py show 2 0 25   # round 2, items 0..24

For an answerable question it shows: the question, the gold answer, the answer page's heading lines, the
column-header lines above the answer's row (lines naming years or periods), and the row itself.
For a "not found" question it shows the question and every line on the shown pages that mentions the item's
words or the period's year, so the reviewer can confirm the answer really isn't there.
Verdicts are recorded by the reviewer in qc/handcheck_v1.jsonl.
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parent / "dataset"
SEED_BASE = 20261115  # round r uses seed SEED_BASE + r (round 1: 20261116)
PER_SLICE = {"S1": 13, "S2": 13, "S3": 13, "S4": 13, "S5": 12, "S6": 12, "S7": 12, "S8": 12}
HEADER = re.compile(
    r"\b(19|20)\d\d\b|months ended|year ended|years ended|as of|at (january|february|march|april|"
    r"may|june|july|august|september|october|november|december)",
    re.I,
)


def load():
    qs = [json.loads(line) for line in (DATA / "questions.jsonl").open()]
    pages = {p["id"]: p for p in map(json.loads, (DATA / "pages.jsonl").open())}
    return qs, pages


def sample(round_no: int) -> None:
    qs, _ = load()
    seed = SEED_BASE + round_no
    rnd = random.Random(seed)
    chosen = []
    for s, n in PER_SLICE.items():
        chosen += rnd.sample([q["id"] for q in qs if q["slice"] == s], n)
    out = HERE / f"handcheck_sample_v{round_no}.json"
    record = {"round": round_no, "seed": seed, "per_slice": PER_SLICE, "ids": chosen}
    out.write_text(json.dumps(record, indent=2))
    print(f"{len(chosen)} questions -> {out}")


def show(round_no: int, start: int, end: int) -> None:
    qs, pages = load()
    by_id = {q["id"]: q for q in qs}
    ids = json.loads((HERE / f"handcheck_sample_v{round_no}.json").read_text())["ids"][start:end]
    for k, qid in enumerate(ids, start):
        q = by_id[qid]
        g = q["gold"]
        print(
            f"\n### [{k}] {qid} {q['slice']}{q['subtype'] or ''} {q['ticker']} {q['form']} "
            f"(report date {q['report_date']})"
        )
        print(f"Q: {q['question']}")
        if g["status"] == "found":
            per = g["period"]
            print(
                f"GOLD: {g['display']} {g['unit']} (scale {g['scale']}, negative={g['negative']}) "
                f"period {per['start'] or ''}..{per['end'] or per['instant']} dims={g['dims'] or '-'}"
            )
            e = g["evidence"][0]
            lines = pages[e["page"]]["text"].split("\n")
            i = lines.index(e["line"])
            print("  page head: " + " | ".join(lines[:4])[:200])
            headers = [ln for ln in lines[max(0, i - 25) : i] if HEADER.search(ln) and len(ln) < 220][-4:]
            for h in headers:
                print(f"  header:   {h[:200]}")
            print(f"  ROW:      {e['line'][:240]}")
        else:
            per = g["period"]
            year = (per["end"] or per["instant"] or "")[:4]
            words = [w for w in re.findall(r"[a-z]{5,}", g["label"].lower())][:4]
            span = f"{per['start'] or ''}..{per['end'] or per['instant']}"
            print(f"GOLD: not_found  (item '{g['label']}', period {span})")
            hits = 0
            for pid in q["pages"]:
                for ln in pages[pid]["text"].split("\n"):
                    low = ln.lower()
                    if sum(w in low for w in words) >= max(1, len(words) - 1) or (
                        year and year in ln and len(ln) < 160
                    ):
                        print(f"  {pid.split('#')[1]}: {ln[:200]}")
                        hits += 1
                        if hits >= 8:
                            break
            if not hits:
                print("  (no line on the shown pages mentions the item's words or the period's year)")


if __name__ == "__main__":
    if sys.argv[1] == "sample":
        sample(int(sys.argv[2]))
    else:
        show(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
