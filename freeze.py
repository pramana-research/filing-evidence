"""Freeze the Filing-Evidence dataset (PROTOCOL.md §11) once a hand-check round has passed.

    python freeze.py 4      # the passing QC round

Writes dataset/FROZEN.json with:
- `fingerprint`: sha256 over the questions sorted by id, each contributing its id, its gold (status, value,
  unit, scale, period, dims, evidence) and the texts of the pages it shows. Every result cites it.
- the sha256 of each dataset file, the passing round's verdict file and its score.

`python freeze.py --check` recomputes the fingerprint and fails if the dataset has changed since the freeze.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "dataset"
ACCEPT = 98  # PROTOCOL §11: at least 98 of 100 hand-checked questions correct


def fingerprint() -> str:
    qs = sorted((json.loads(line) for line in (DATA / "questions.jsonl").open()), key=lambda q: q["id"])
    pages = {p["id"]: p["text"] for p in map(json.loads, (DATA / "pages.jsonl").open())}
    h = hashlib.sha256()
    for q in qs:
        g = q["gold"]
        record = {
            "id": q["id"],
            "gold": {k: g.get(k) for k in ("status", "value", "unit", "scale", "period", "dims", "evidence")},
            "pages": [pages[p] for p in q["pages"]],
        }
        h.update(json.dumps(record, sort_keys=True, ensure_ascii=False).encode())
        h.update(b"\n")
    return h.hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(round_no: int) -> int:
    verdicts = [json.loads(line) for line in (HERE / "qc" / f"handcheck_v{round_no}.jsonl").open()]
    score = sum(v["correct"] for v in verdicts)
    if len(verdicts) != 100 or score < ACCEPT:
        print(f"round {round_no}: {score}/{len(verdicts)}; below the acceptance bar, not freezing")
        return 1
    sample = json.loads((HERE / "qc" / f"handcheck_sample_v{round_no}.json").read_text())
    stats = json.loads((DATA / "stats.json").read_text())
    record = {
        "fingerprint": fingerprint(),
        "frozen_on": date.today().isoformat(),
        "questions": stats["questions"] if "questions" in stats else None,
        "draft_fingerprint": stats["draft_fingerprint"],
        "qc": {
            "round": round_no,
            "seed": sample["seed"],
            "correct": score,
            "of": len(verdicts),
            "gold_values_correct": sum(v["gold_value_correct"] for v in verdicts),
            "verdicts": f"qc/handcheck_v{round_no}.jsonl",
        },
        "files": {
            p.name: file_sha(p)
            for p in sorted(DATA.iterdir())
            if p.suffix in {".jsonl", ".json"} and p.name != "FROZEN.json"
        },
    }
    (DATA / "FROZEN.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


def check() -> int:
    frozen = json.loads((DATA / "FROZEN.json").read_text())
    now = fingerprint()
    ok = now == frozen["fingerprint"]
    print(f"{'OK' if ok else 'CHANGED'}: {now}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(check() if sys.argv[1] == "--check" else freeze(int(sys.argv[1])))
