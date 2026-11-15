# Filing-Evidence benchmark: protocol (pre-registration)

| | |
|---|---|
| Version | **1.0-draft**, 2026-11-15. Rendering and eligibility rules (§5) refined the same day while building the reader, before any question existed |
| Status | written **before** any benchmark results exist. Changes after the first results are logged in §12 |
| Owner | pramana-research |
| Working name | Filing-Evidence (final name to be decided before publication) |

This document fixes the question, data, setups, metrics and analysis in advance, so the results can't be shaped
after the fact. Anyone should be able to rerun the benchmark from this document plus the code.

---

## 1 · Research questions

- **RQ1.** How reliably do ~10B-parameter open instruct models extract a requested number from an SEC filing **with
  evidence that can be checked automatically** (the page and the verbatim line), and answer "not found" when the
  number isn't in the provided pages?
- **RQ2.** Where do they fail? Which kinds of filing content (slices, §4) and which error types (§9)?
- **RQ3.** How much do two cheap, training-free interventions help: **(a)** automatic checking with one retry,
  **(b)** the model's own thinking/reasoning mode? At what cost in tokens and time?

Not in scope: training or fine-tuning, finance-specific models, models that don't fit one 24 GB GPU, charts and scanned pages.

---

## 2 · Models

Ten general instruct models, **each from a different company**, all run on one NVIDIA RTX 4090 (24 GB).

| # | Company | HF repository |
|---|---|---|
| 1 | Alibaba | `Qwen/Qwen3.5-9B` (fallback `Qwen/Qwen3-8B` if it can't be served; recorded as a deviation) |
| 2 | IBM | `ibm-granite/granite-4.2-8b` |
| 3 | Mistral | `mistralai/Ministral-3-8B-Instruct-2512` |
| 4 | AllenAI | `allenai/Olmo-3-7B-Instruct` |
| 5 | NVIDIA | `nvidia/NVIDIA-Nemotron-Nano-9B-v2` |
| 6 | OpenAI | `openai/gpt-oss-20b` |
| 7 | Microsoft | `microsoft/phi-4` |
| 8 | Google | `google/gemma-3-12b-it` |
| 9 | Zhipu (Z.ai) | `zai-org/GLM-4.6V-Flash` |
| 10 | Meta | `meta-llama/Llama-3.1-8B-Instruct` |

- **Pinned revision:** the exact HF commit of each model is recorded at run time and never changed during the study.
- **Precision:** bf16 when weights plus an 8,192-token context fit in 24 GB; otherwise FP8 (weights quantised by vLLM
  at load). gpt-oss-20b uses its native MXFP4 weights. The precision used is reported for every model.
- **Excluded by design:** fine-tuned or domain-specific models (not like-for-like); a second model from the same company.

---

## 3 · Data

### 3.1 Companies (40, nine sector groups)

| Group | Companies |
|---|---|
| Technology | AAPL, MSFT, NVDA, ORCL, ADBE |
| Banks | JPM, BAC, WFC, USB, PNC |
| Other financials | GS, SCHW, AXP |
| Insurance | PGR, TRV, ALL, MET |
| REITs | PLD, O, SPG |
| Utilities | NEE, DUK, SO |
| Healthcare | JNJ, UNH, PFE, LLY, TMO |
| Consumer | WMT, COST, HD, MCD, KO |
| Industrials, defence, energy, telecom, media | CAT, HON, UPS, LMT, CVX, VZ, DIS |

ExxonMobil (XOM) was considered and replaced by Chevron (CVX) before any data was built: the SEC submissions record
for XOM's ticker starts on 2026-07-01 and contains no 10-K (checked 2026-11-15). Lockheed Martin (LMT) completes the 40.

Insurers, REITs, utilities and banks are included on purpose: their statements use layouts and line items
unlike industrial companies (e.g. "Statement of Financial Condition", net premiums earned, funds from operations).

### 3.2 Filings

For each company: the **most recent 10-K and the most recent 10-Q filed on or before 2026-11-15**, as listed by
the SEC submissions API: about 80 filings. The primary document (inline XBRL HTML) is downloaded once from
`sec.gov/Archives` with an identifying User-Agent, at most 5 requests per second. It's stored with its accession
number and sha256 in forge-data, and listed in `dataset/manifest.json`.

### 3.3 Answer key

Gold answers come from the filing's own **inline XBRL** (`ix:nonFraction`) tags: concept, value (after the `scale`
and `sign` attributes and the `format` transform), unit, period (from the tag's context) and dimensions
(segment members), plus the **page and line where the tagged number is displayed**. Hidden facts (inside
`ix:header`) are excluded, because they aren't visible to a reader. Values tagged in several places are correct on
any page where they're displayed.

### 3.4 Contamination note

Models may have seen older filings during pretraining. Using the most recent filings (mostly filed in 2026)
reduces this. For each model we report its release date next to the filing dates. A memorised answer still
has to come with a verbatim quote from the provided pages, which the checker enforces.

---

## 4 · Slices (125 questions each, 1,000 total)

| Slice | Definition | Example question |
|---|---|---|
| **S1** Main statements, current period | non-dimensional fact on a primary statement page (income / operations, balance sheet / financial condition, cash flows), latest period | "What were total revenues for the fiscal year ended January 31, 2026?" |
| **S2** Main statements, prior period | as S1, but a prior-period column on the same page | the same, for FY2025 |
| **S3** 10-Q quarter vs year-to-date | 10-Q facts where the page shows both a 3-month and a year-to-date column; the question asks for one explicitly | "…for the three months ended September 30, 2026?" |
| **S4** Notes | non-dimensional facts displayed on pages after the primary statements, in tables | "What was the fair value of long-term debt at December 31, 2025?" |
| **S5** Segments | facts with a segment dimension (e.g. `StatementBusinessSegmentsAxis`) | "What was operating income for the Sam's Club U.S. segment…?" |
| **S6** Numbers in prose | facts displayed inside a sentence (a line of ≥ 20 words), typically MD&A | "By how much did net sales increase…?" phrased as the tagged quantity |
| **S7** Units and per-share | per-share amounts, share counts, percentages, or values whose display scale differs from the page's headline scale | "What was diluted EPS…?" |
| **S8** Not in the provided pages | an item or period that is **not** in the three pages given: (a) a period not shown, (b) an item the company doesn't report, (c) a quarter asked of a 10-K, (d) an item that exists elsewhere in the filing but not on the given pages | correct answer: `not_found` |

**Sampling rules** (fixed random seed 20261115):
- at most 30 questions per company;
- each slice drawn from at least 15 companies;
- 10-K and 10-Q balanced where the slice allows;
- S8 split evenly across (a)–(d).

If a slice can't reach 125 under these rules, companies are added (logged in §12). The bar is never lowered.

**Question wording:** templates are filled with the concept's label from the filing's own label linkbase
(dimension members likewise), the company name, and the period in words. Templates are listed in `builder.py`
and fixed before results.

---

## 5 · What the model sees

- **Pages:** each question comes with **three pages** of the same filing: the page displaying the answer, an adjacent
  page, and a random distractor page. For S8, three pages that don't contain the answer. Pages are numbered
  as in the document's page breaks. Page order is randomised per question with the fixed seed.
- **Page text:** derived from the HTML by one fixed rendering (`src/forge/domains/finance/data/ixbrl.py`):
  - pages follow the document's page-break markup;
  - block elements end a line, **except inside a table cell**, so a table row renders as one line even when the
    filer wraps each cell's content in `<div>`/`<p>`;
  - table cells are separated by two spaces; whitespace is collapsed;
  - text inside `ix:header` and `<script>`/`<style>` is never shown;
  - a page longer than ~3,000 tokens (a document with no page-break markup, or an oversized page such as an exhibit
    index) is split at line boundaries into consecutive pages of ~1,500 tokens.

  Questions whose answer page or distractor pages exceed 3,000 tokens (Qwen tokenizer count, as a common
  yardstick) are excluded before sampling, so no model sees truncated or oversized pages.
- **Which facts can become questions:** only facts displayed as digits (not "—" or words such as "two"), and only
  where the displayed line carries a label (at least two words), so the evidence line identifies the item. In S5,
  only segment dimensions (axes ending in `SegmentsAxis`) are used. Equity-statement component columns are excluded
  as ambiguous even for a human reader.
- **Instructions (prompt v1):** fixed text in `prompts/v1.txt`, identical for all models. It asks for one JSON object:

```json
{"status": "found", "value": 15511, "scale": "in millions", "page": 54,
 "span": "<the exact line from the page containing the number>"}
```

or `{"status": "not_found"}`, using only the provided pages. One worked example (on a made-up filing) is included.

---

## 6 · Setups

| Setup | Definition |
|---|---|
| **C1 Plain** | the model's default non-reasoning mode; one answer |
| **C2 Check + retry** | C1, then the automatic check (§7). If the answer fails a check, the model is told *which* check failed (fixed messages in `prompts/v1_retry.txt`) and answers once more. The second answer is final |
| **C3 Thinking** | the model's own reasoning mode where it has one (e.g. Qwen `enable_thinking`, gpt-oss reasoning effort "high"); one answer. Models without one are reported as "n/a" |

**Decoding:** temperature 0; max new tokens 512 (C1/C2), 8,192 (C3). Each model's own chat template is applied by
vLLM. Exact server commands are recorded per model.

---

## 7 · Automatic checks (the checker)

An answer **passes** when all hold:
1. it parses as the JSON contract;
2. `page` is one of the three provided pages;
3. `span`, with whitespace normalised, occurs verbatim on that page;
4. the **answered** `value` appears in `span` as displayed (thousands separators, parentheses for negatives and `$` ignored).

C2's retry and the confident-wrong metric both use exactly this check.

---

## 8 · Metrics

**Per question, one outcome:**

| Outcome | Meaning |
|---|---|
| **correct** | status found, value equals gold (after scale; per-share and percent values compared as displayed), and the checks pass |
| **confident-wrong** | the checks pass but the value isn't gold: **the dangerous case** |
| caught-wrong | value not gold and a check fails (an automated system would reject it) |
| unverifiable-right | value equals gold but a check fails (right number, unusable evidence) |
| missed | `not_found` on an answerable question |
| abstained-correctly / invented | on S8: `not_found` / anything found |
| invalid | output doesn't parse |

**Headline metrics per model × setup:**
- **accuracy** = correct ÷ answerable (S1–S7);
- **confident-wrong rate** over all 1,000;
- **abstention accuracy** on S8;
- **coverage at zero confident-wrong**, where it applies.

**Also reported:**
- per-slice accuracy;
- the error taxonomy (§9);
- mean and p95 tokens and seconds per answer;
- retry rate (C2).

---

## 9 · Error taxonomy

Every non-correct answer is assigned by code to one category:
- wrong line quoted;
- wrong page cited;
- span not verbatim;
- scale or unit error;
- wrong period or column;
- wrong item;
- invented on S8;
- missed;
- invalid format.

A sample of 20 per model is reviewed by hand to confirm the coded category. Disagreements are reported.

---

## 10 · Statistics

- **Ranges:** 95% Wilson intervals for every rate.
- **Comparing setups within a model (C1 vs C2 vs C3):** paired exact McNemar tests on the same questions.
- **Comparing models:** intervals, and paired McNemar on the full set. No claim of "better" without a significant
  paired difference (α = 0.05, Holm-corrected within each family of comparisons).

---

## 11 · Quality control before any model runs

- **Hand check:** 100 questions (stratified across all eight slices) are checked by hand against the rendered filing
  (gold value, period, page, wording). **Acceptance: ≥ 98 correct.** Otherwise the builder is fixed and a new sample drawn.
- **Smoke test:** Qwen3-8B on the 19 Walmart probe questions must reproduce the probe's results within the noise
  of the rendering change (§12 notes any difference).
- **Freeze:** the dataset is frozen and fingerprinted (sha256 of the sorted question ids, gold values and page
  texts). All results cite the fingerprint.

---

## 12 · Deviations log

Any change to this protocol after the first model result is recorded here: date, change, reason, and the effect on results.

| Date | Change | Reason |
|---|---|---|
| — | — | — |

---

## 13 · Publication

Everything is published under pramana-research:
- this protocol;
- the code;
- the frozen dataset (questions, gold, page texts, manifest of SEC sources);
- every model answer;
- the per-model reports;
- the overarching report.

SEC filings are public records. Model outputs are released with each model's licence noted.
