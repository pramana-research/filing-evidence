---
pretty_name: Filing-Evidence
license: cc-by-4.0
language: [en]
task_categories: [question-answering]
tags: [finance, sec-filings, xbrl, evidence, benchmark]
size_categories: [1K<n<10K]
configs:
  - config_name: questions
    data_files: dataset/questions.jsonl
  - config_name: pages
    data_files: dataset/pages.jsonl
---

# Filing-Evidence (data)

The data half of the Filing-Evidence benchmark. Code, protocol and run records:
[github.com/pramana-research/filing-evidence](https://github.com/pramana-research/filing-evidence).

| Path | What |
|---|---|
| `dataset/questions.jsonl` | 1,000 questions: slice, wording, the three pages shown, gold answer (value, scale, unit, period, evidence page and line) |
| `dataset/pages.jsonl` | the text of every page shown, keyed by page id |
| `results/<set>/<model>/<setup>/answers.jsonl` | for each model and setup: every request, raw reply (and reasoning), parsed answer, failed check, outcome |
| `logs/serve-<model>.log` | the vLLM server log of each model's run |

The questions and pages are frozen: their fingerprint is
`4fa8f252292167fb42efdc8ec1eed12c63eaf74cfdccd8f446cbe12b81323c0a`, recorded in git (`dataset/FROZEN.json`) before
any model ran. `python hf_data.py pull` in the code repo downloads this dataset and verifies it.

Source: SEC EDGAR filings (public records), most recent 10-K and 10-Q of 45 US companies filed on or before
2026-11-15.

Licence: CC BY 4.0, Copyright 2026 Pramana Research. Model outputs remain subject to
the licence of the model that produced them. Paper: https://pramana-research.com/research/filing-evidence (a community research report, not peer-reviewed)
