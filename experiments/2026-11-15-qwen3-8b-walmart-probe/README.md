# Probe: base Qwen3-8B on a real 10-K (Walmart FY2026), 2026-11-15

**Question:** can an untrained ~8B open model extract numbers from a real SEC filing with checkable evidence
(page and verbatim line), and say "not found" when the number isn't there?

**Status:** preliminary (1 company, 19 questions). Superseded by the filing-evidence benchmark, but kept as the
first data point; its 19 questions become a subset of that benchmark.

## Setup
| Item | Value |
|---|---|
| Model | `Qwen/Qwen3-8B` (base, untrained), vLLM, bf16, temperature 0 |
| Filing | Walmart Inc. 10-K, fiscal year ended 2026-01-31, SEC accession `0000104169-26-000055`, primary document `wmt-20260131.htm` |
| Filing sha256 | `ec79a926cd42f64d81029026077fa4d17a0d8d8072dcbce585d23c5045f48ffc` (stored in forge-data: `data/finance/filings/WMT/`) |
| Answer key | the filing's own inline-XBRL tags (value, period, scale, location); non-dimensional facts only |
| Questions | 16 answerable (8 line items × FY2026 and FY2025, income statement + balance sheet) + 3 "not found" traps |
| Context | 3 pages per question: the answer's page, its neighbour, a random distractor page |
| Setups | thinking off, thinking on |

## Results
| | Thinking off | Thinking on |
|---|---|---|
| Correct with checkable evidence | 15 / 19 | 17 / 19 |
| "Not found" traps | 3 / 3 | 3 / 3 |
| Wrong-year column picked | 0 | 0 |
| Wrong values that would pass a proper checker | 0 | 0 |
| Tokens per answer | ~60 | ~400–2,300 |

The misses: quoted the neighbouring line (value right); page off by one; added a "$" not in the text; diluted EPS
2.73 read as 273 "in millions"; an over-reasoned derived value (30,803 vs 33,401). Note on the grader: it labelled
two misses "confident-wrong" because it checked the *gold* value against the quote; a proper checker tests the
*answered* value, which catches both. The benchmark's checker does this correctly.

## Reproduce
```bash
bash src/forge/core/serve/serve.sh Qwen/Qwen3-8B qwen3-base          # vLLM on :8000
python -I research/experiments/2026-11-15-qwen3-8b-walmart-probe/probe.py \
  <forge-data>/data/finance/filings/WMT/0000104169-26-000055/wmt-20260131.htm \
  http://localhost:8000/v1 qwen3-base off results_thinking_off.json   # and: on results_thinking_on.json
```
Code at forge commit `00cdefe` (uncommitted when run).

## Files
`probe.py` (exact code), `results_thinking_off.json`, `results_thinking_on.json` (every question, reply and verdict).

## Licence
SEC filings are public. The code is part of forge.
