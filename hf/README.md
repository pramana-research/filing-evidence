---
pretty_name: Filing-Evidence
license: cc-by-4.0
language: [en]
task_categories: [question-answering]
tags: [finance, sec-filings, xbrl, evidence, benchmark, arxiv:2611.24990]
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
the licence of the model that produced them. Paper: https://pramana-research.com/research/filing-evidence, also on arXiv as
[arXiv:2611.24990](https://arxiv.org/abs/2611.24990) (a community research report, not peer-reviewed)

## Citation

```bibtex
@misc{pramana2026filingevidence,
  title         = {Show Your Work: Can Small Open Models Read SEC Filings with Evidence a Machine Can Check?},
  author        = {Nandula, Krishna},
  organization  = {Pramana Research},
  year          = {2026},
  eprint        = {2611.24990},
  archivePrefix = {arXiv},
  primaryClass  = {cs.SE},
  doi           = {10.48550/arXiv.2611.24990},
  url           = {https://arxiv.org/abs/2611.24990}
}
```

## Disclaimer

This is an independent community research report, written in a personal capacity; it does not represent the views of any employer or other organisation. It is not affiliated with, sponsored or endorsed by any company or model developer named here; all names and trademarks belong to their owners. Results describe specific model versions under one fixed setup and are not a general judgement of any model. The data, results and code are provided as is, without warranty, and may contain errors; check any figure against the original filing. Nothing here is financial, investment or legal advice.
