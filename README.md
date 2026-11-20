# Filing-Evidence

Can small open models pull a number out of an SEC filing **with evidence a machine can check** (the page and the
verbatim line), and say "not found" when it isn't there?

1,000 questions over 90 recent 10-K / 10-Q filings of 45 US companies, with gold answers taken from the filings'
own inline XBRL tags. Ten open models from ten companies, each run on one RTX 4090 with vLLM, in three setups:
plain (C1), check + retry (C2) and thinking (C3). Everything was pre-registered in [PROTOCOL.md](PROTOCOL.md)
before any model ran; later changes are logged in its §12.

**Code and record here, data on Hugging Face.** Questions, page texts, every model reply and the server logs are in
the Hugging Face dataset [`pramana-research/filing-evidence`](https://huggingface.co/datasets/pramana-research/filing-evidence).
Git holds the code, the protocol, the QC reviews, the dataset fingerprint (`dataset/FROZEN.json`) and each
run's `summary.json` / `run.json`.

**Paper:** [Show Your Work: Can Small Open Models Read SEC Filings with Evidence a Machine Can Check?](https://pramana-research.com/research/filing-evidence)
(with a page per model and PDFs), also on arXiv as [arXiv:2611.24990](https://arxiv.org/abs/2611.24990) [cs.SE]
(DOI [10.48550/arXiv.2611.24990](https://doi.org/10.48550/arXiv.2611.24990)). An independent community research
report: not peer-reviewed, and not submitted to or accepted by any conference or journal.

## Layout

| Path | What |
|---|---|
| `PROTOCOL.md` | the pre-registration: questions, data, setups, checks, metrics, statistics, deviations |
| `fetch.py`, `builder.py`, `ixbrl.py`, `edgar.py` | download the filings from SEC EDGAR and build the questions |
| `qc/`, `freeze.py`, `dataset/FROZEN.json` | AI-assisted reviews of 100 questions per round (see PROTOCOL §12), then the frozen fingerprint |
| `checker.py` | the automatic checks (§7), outcomes (§8), error categories (§9), metrics |
| `prompts/`, `models.yaml`, `templates/` | the prompt, the retry messages, how each model is served and asked |
| `serve.py`, `runner.py`, `run_all.sh`, `loadcheck.sh` | serve a model with vLLM, run a setup, run everything |
| `watchdog.sh` | GPU guard rail for unattended runs |
| `results/<set>/<model>/<setup>/` | `summary.json`, `run.json` (answers on Hugging Face) |
| `report/` | the paper and model pages: statistics, charts, templates, PDF build |
| `smoke/`, `experiments/` | the 19-question smoke set; the 2026-11-15 probe that motivated the benchmark |

## Reproduce

```bash
uv sync --all-extras                      # Python 3.12; vLLM 0.33.0 for serving
cp .env.example .env                      # HF_TOKEN for gated models
uv run python hf_data.py pull             # questions, pages, all replies; verified against dataset/FROZEN.json
uv run pytest                             # checker, builder and reader tests

# re-grade every stored reply (no GPU)
uv run python runner.py qwen3.5-9b C1 --regrade

# run a model yourself (one 24 GB GPU)
bash run_all.sh qwen3.5-9b
```

Rebuild the paper and model pages (every number is computed from the stored replies) into a checkout of the site:

```bash
uv run python report/build.py --out ../pramana-research-landing   # research/** HTML
bash report/pdf.sh ../pramana-research-landing                      # PDFs (headless Chrome)
```

Rebuilding the dataset from SEC EDGAR (`fetch.py`, then `builder.py`) needs `SEC_USER_AGENT` in `.env`; the result
is checked against the same fingerprint.

## How to cite

```bibtex
@misc{pramana2026filingevidence,
  title         = {Show Your Work: Can Small Open Models Read SEC Filings with Evidence a Machine Can Check?},
  author        = {Nandula, Krishna},
  organization  = {Pramana Research},
  year          = {2026},
  month         = {nov},
  eprint        = {2611.24990},
  archivePrefix = {arXiv},
  primaryClass  = {cs.SE},
  doi           = {10.48550/arXiv.2611.24990},
  url           = {https://arxiv.org/abs/2611.24990},
  note          = {Community research report, not peer-reviewed. Filing-Evidence benchmark, version 1.0}
}
```

GitHub's "Cite this repository" button reads [CITATION.cff](CITATION.cff).

## Licence

Open source.

- **Code:** [Apache License 2.0](LICENSE).
- **Text, figures, questions, answer key and model outputs:** [CC BY 4.0](LICENSE-DATA.txt): share and adapt for
  any purpose, with attribution. Model outputs remain subject to each model's own licence.
- SEC filings are public records.

Copyright 2026 Pramana Research. See [NOTICE](NOTICE).

## Disclaimer

This is an independent community research report, written in a personal capacity; it does not represent the views of any employer or other organisation. It is not affiliated with, sponsored or endorsed by any company or model developer named here; all names and trademarks belong to their owners. Results describe specific model versions under one fixed setup and are not a general judgement of any model. The data, results and code are provided as is, without warranty, and may contain errors; check any figure against the original filing. Nothing here is financial, investment or legal advice.
