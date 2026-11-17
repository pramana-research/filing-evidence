"""Build the smoke-test set (PROTOCOL.md §11): the 19 questions of the 2026-11-15 Walmart probe
(research/experiments/2026-11-15-qwen3-8b-walmart-probe), rebuilt with the benchmark's reader and schema.

    python smoke.py      # -> smoke/questions.jsonl, smoke/pages.jsonl

Same items as the probe: 8 line items x the two latest fiscal years (16 answerable), plus three "not found"
traps (an absent year, an item Walmart doesn't report, a quarter asked of a 10-K). Same page rule: the
answer's page, the page before it, and a random distractor (seed 0). The pages now come from the benchmark's
rendering, so page numbers differ from the probe's; the smoke test asks whether Qwen3-8B's results reproduce
"within the noise of the rendering change", not whether every page number matches.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import builder as B  # noqa: E402

ACCESSION = "0000104169-26-000055"  # Walmart 10-K, fiscal year ended 2026-01-31 (the probe's filing)
WANT = [  # (concept, label in plain words): the probe's list
    ("us-gaap:Revenues", "total revenues"),
    ("us-gaap:OperatingIncomeLoss", "operating income"),
    ("us-gaap:NetIncomeLoss", "consolidated net income attributable to Walmart"),
    ("us-gaap:ProfitLoss", "consolidated net income (including noncontrolling interest)"),
    ("us-gaap:EarningsPerShareDiluted", "diluted net income per share attributable to Walmart"),
    ("us-gaap:CashAndCashEquivalentsAtCarryingValue", "cash and cash equivalents"),
    ("us-gaap:Assets", "total assets"),
    ("us-gaap:LongTermDebtNoncurrent", "long-term debt (excluding amounts due within one year)"),
]


def main() -> int:
    from transformers import AutoTokenizer

    from ixbrl import read_document_set, read_labels
    from paths import data_dir

    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", local_files_only=True)
    manifest = json.loads((HERE / "dataset" / "manifest.json").read_text())
    f = next(x for x in manifest["filings"] if x["accession"] == ACCESSION)
    folder = data_dir() / "finance" / "filings" / f["ticker"] / ACCESSION
    texts = {
        d["name"]: (folder / d["name"]).read_text(encoding="utf-8", errors="replace")
        for d in f["files"]["documents"]
    }
    labels = read_labels(
        (folder / f["files"]["labels"]["name"]).read_text(encoding="utf-8", errors="replace")
    )
    name = f["primary_document"]
    parsed = read_document_set(texts)[name]
    doc = B.Doc(
        "WMT",
        "Walmart Inc.",
        "10-K",
        ACCESSION,
        f["report_date"],
        name,
        parsed.pages,
        parsed.facts,
        parsed.contexts,
        labels,
    )
    doc.page_tokens = [B.tokens(p, tok) for p in doc.pages]
    rnd = random.Random(0)

    def pages_for(page: int) -> list[int]:
        others = [
            i
            for i, t in enumerate(doc.page_tokens)
            if i != page and t <= B.MAX_TOKENS and len(doc.pages[i]) > 400
        ]
        shown = sorted({page, max(0, page - 1), rnd.choice(others)})
        rnd.shuffle(shown)
        return shown

    items = []
    for concept, label in WANT:
        by_end = {}
        for fact in doc.facts:
            ctx = doc.contexts[fact.context]
            if fact.concept != concept or ctx.dims or not fact.occurrences:
                continue
            if ctx.start and B.days(ctx.start, ctx.end) and not 357 <= B.days(ctx.start, ctx.end) <= 371:
                continue
            by_end.setdefault(ctx.period_end, fact)
        for end in sorted(by_end, reverse=True)[:2]:  # current and prior year (the column trap)
            fact = by_end[end]
            ctx = doc.contexts[fact.context]
            shown = pages_for(fact.occurrences[0].page)
            period = B.period_phrase(ctx.start, ctx.end, ctx.instant, "10-K")
            items.append(
                {
                    "key": f"{concept.split(':')[1]}@{end}",
                    "label": label,
                    "period": period,
                    "pages": shown,
                    "gold": B.gold(doc, fact, shown, label),
                }
            )
    ni = next(i for i in items if i["key"].startswith("NetIncomeLoss"))
    rev = next(i for i in items if i["key"].startswith("Revenues"))
    absent = [
        (
            "NetIncome@FY2019 (absent year)",
            ni["label"],
            "for the fiscal year ended January 31, 2019",
            ni["pages"],
            "a",
            {"start": "2018-02-01", "end": "2019-01-31", "instant": None},
        ),
        (
            "R&D expense (not reported)",
            "research and development expense",
            rev["period"],
            rev["pages"],
            "b",
            rev["gold"]["period"],
        ),
        (
            "Revenues Q3 (quarter asked of a 10-K)",
            "total revenues",
            "for the three months ended October 31, 2025",
            rev["pages"],
            "c",
            {"start": "2025-08-01", "end": "2025-10-31", "instant": None},
        ),
    ]
    for key, label, period, shown, kind, per in absent:
        items.append(
            {
                "key": key,
                "label": label,
                "period": period,
                "pages": shown,
                "kind": kind,
                "gold": {"status": "not_found", "label": label, "period": per},
            }
        )

    out = HERE / "smoke"
    out.mkdir(exist_ok=True)
    used = {}
    with (out / "questions.jsonl").open("w") as fh:
        for n, it in enumerate(items, 1):
            for p in it["pages"]:
                used[doc.page_id(p)] = {
                    "id": doc.page_id(p),
                    "ticker": "WMT",
                    "form": "10-K",
                    "accession": ACCESSION,
                    "document": name,
                    "page": p,
                    "tokens": doc.page_tokens[p],
                    "text": doc.pages[p],
                }
            row = {
                "id": f"SMOKE-{n:02d}",
                "probe_item": it["key"],
                "slice": "S8" if it["gold"]["status"] == "not_found" else "S1",
                "subtype": it.get("kind"),
                "ticker": "WMT",
                "company": "Walmart Inc.",
                "form": "10-K",
                "accession": ACCESSION,
                "document": name,
                "report_date": f["report_date"],
                "question": f"What was Walmart Inc.'s {it['label']} {it['period']}?",
                "pages": [doc.page_id(p) for p in it["pages"]],
                "page_labels": list(it["pages"]),
                "gold": it["gold"],
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out / "pages.jsonl").open("w") as fh:
        for p in sorted(used.values(), key=lambda r: r["page"]):
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"{len(items)} questions, {len(used)} pages -> {out}")
    for it in items:
        g = it["gold"]
        print(f"  {it['key']:42s} {g.get('display', 'not_found'):>10s}  pages {it['pages']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
