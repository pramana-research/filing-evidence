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

### 3.1 Companies (45: forty in nine sector groups, plus five added for segment coverage)

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

**Added 2026-11-16 for segment coverage:** PEP, ABT, GD, CMCSA, MDT (45 companies, about 90 filings). Under the
final wording rules S5 reached 123 of 125 questions from only 17 companies; per §4 companies are added rather than
the bar lowered. Logged before any model result.

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
| **S6** Numbers in prose | facts displayed inside a sentence (a line of ≥ 20 words, not counting figures or currency signs), typically MD&A or notes | "By how much did net sales increase…?" phrased as the tagged quantity |
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
- **Answerability rules** (added after QC round 1, §11; all before any model result). A question is only built when
  a careful reader of the shown pages could answer it without guessing:
  - the figure is a column figure, not a number inside the row's wording ("…net of tax of $1 and $3…");
  - its row is not *sparse* (fewer figures than the widest row of its table: blank columns can't be mapped in plain
    text, e.g. Schedule III segment rows);
  - its row does not show other items for the same period (e.g. a stock-option row with count, price, term and
    intrinsic value), nor same-period figures split by category;
  - the answer page shows the period's year (e.g. not "Fiscal 2025" columns for a year ending February 2026).
- **Wording rules:** the item is named by its row label as printed, if that label is unique on the shown pages;
  parentheticals with figures ("(Note 6)", "(includes $59,758…)"), unit suffixes ("(in shares)") and glued footnote
  markers are removed. Labels of three words or fewer, and bare percentages, get their section heading
  ("deposits (interest expense)"). Otherwise the filer's XBRL label is used, only if it isn't in the inverted
  taxonomy style ("Premiums Written, Net") and most of its words appear in the evidence line. Segment questions use
  the row label when the row is the item (segments as columns). Non-dollar units are stated ("(number of shares)",
  "(per share)", "(%)"). Every question text is unique.
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

**Sign is not graded.** The filing's display convention and XBRL's sign often disagree (a cash-flow line shows
"(6,716)" for a positive XBRL value, or "682" for a negative one), and the model reads the display. An answer is
compared with the displayed magnitude; a sign the model adds or omits is neither rewarded nor penalised.

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

  | Round | Sample seed | Result | Outcome |
  |---|---|---|---|
  | 1 | 20261116 | **87 / 100**. Every gold *value* was correct; the 13 failures were wording or answerability: missing section context (5), sparse rows (3), parentheticals cut mid-label (2), a multi-measure row (1), misleading labels (2) | builder fixed (answerability and wording rules, §5); verdicts in `qc/handcheck_v1.jsonl` |
  | 2 | 20261117 | **76 / 100**. Every gold *value* correct again (200 / 200 over both rounds). The round-1 section-context rule over-reached: headings attached to totals and below-the-line rows (12), labels cut at dates or dashes (4), labels needing their table's subject (4), a non-unique label falling back to an identical XBRL label, fiscal-year columns named by start year, a prose label not matching its sentence, an ambiguous "not reported" item | wording redesigned: printed row label only, unique on the shown pages, no XBRL fallback for rows; context only from a reliable heading (≤ 6 rows up, no summary row between, not a caption); summary rows never get context; bare totals, balance rows, month-ending and entity-name labels dropped; period month **and day** must be on the answer page; prose labels must match the figure's sentence; "not reported" items share no words with the shown pages. Capacity: in S5 each segment's figure counts as its own item; S8 kind (b) tries up to 8 concepts per filing. S5 still reached only 123 from 17 companies, so (per §4) five companies were added (§3.1) and two over-strict rules corrected: segment facts tagged with `ConsolidationItemsAxis = OperatingSegmentsMember` alongside the segment (common since ASU 2023-07) count as single-segment facts; the sparse-row test compares a row only with the rows of its own table. One-word XBRL labels are allowed for segment questions when they name a standard line item ("Goodwill", "Revenues"), never for change words ("Acquisitions", "Write-offs"). Verdicts in `qc/handcheck_v2.jsonl` |
  | 3 | 20261118 | **96 / 100** (draft ab03bcacd7df932c). Every gold *value* correct (300 / 300 over three rounds); S1–S4 and S8 52 / 52 and 12 / 12. The 4 failures were wording: a footnote marker after a parenthesis kept and a column-header line taken as context (CVX), "Denominator: (b)" taken as context (AXP), a cover-page sentence fragment used as the item name (PGR), and a prose label broader than its sentence (UPS: D&A of property, plant and equipment asked as "depreciation and amortization") | builder fixed: footnote digits after ")" removed; lines containing "Total" or starting with Numerator/Denominator are never headings; footnote markers removed from headings; row labels that start like a sentence (The/A/Our/We…) or mention the registrant are dropped; a prose label followed in its sentence by a narrowing qualifier ("… expense for property, plant and equipment", but not "… for the three months") is dropped. Regression tests for each. Verdicts in `qc/handcheck_v3.jsonl` |
  | 4 | 20261119 | **98 / 100: accepted** (draft 88c0ce313bbcca1c; besides the round-3 fixes, a scan of all 1,000 questions before sampling found and fixed "Numerator –" prefixes on row labels, headings mentioning numerator/denominator, and item names in capitals). Every gold *value* correct (400 / 400 over four rounds). Failures: a status column used as an item without its table's subject (CMCSA "in production and in development"), and a not-found item that names no item (NVDA S8b "due in 2028") | dataset frozen (below). Known, accepted wording blemishes recorded in `qc/handcheck_v4.jsonl` notes: a kept "Less:" prefix; a one-word capitalised label ("NET INCOME"); a segment-subtotal member ("Reportable Segments"); a single-segment company's "Reportable Segment"; roll-forward rows without their table's subject; year-start balances answering a prior year-end date. None changes the correct answer. Verdicts in `qc/handcheck_v4.jsonl` |
- **Smoke test:** Qwen3-8B on the 19 Walmart probe questions must reproduce the probe's results within the noise
  of the rendering change (§12 notes any difference).

  **Passed 2026-11-16** (`smoke.py`, results in `results/smoke/qwen3-8b/`). Thinking off: probe 15 / 19, smoke C1
  16 / 19; thinking on: probe 17 / 19, smoke C3 18 / 19; smoke C2 17 / 19. Zero confident-wrong in every setup, 3 / 3
  traps in every setup. The same failure as the probe recurs (diluted EPS 2.73 answered as 273, caught by the
  value check, not fixed by C2's retry); C2's retry fixed a quoted neighbouring line.
- **Freeze:** the dataset is frozen and fingerprinted (sha256 of the sorted question ids, gold values and page
  texts). All results cite the fingerprint.

  **Frozen 2026-11-16** after round 4: fingerprint
  `4fa8f252292167fb42efdc8ec1eed12c63eaf74cfdccd8f446cbe12b81323c0a` (`dataset/FROZEN.json`, written by `freeze.py 4`;
  `python freeze.py --check` verifies it). From here on, any change to the questions, gold or pages is a deviation
  (§12) and needs a new fingerprint.

---

## 12 · Deviations log

Any change to this protocol after the first model result is recorded here: date, change, reason, and the effect on results.

| Date | Change | Reason |
|---|---|---|
| 2026-11-16 (before any main result) | Served context 16,384 tokens, not 8,192 (§2); the precision rule applies at 16,384 | The longest prompt is ~6.2k tokens (pages ≤ 5,560 + instructions); C3 allows 8,192 new tokens. 8,192 would have truncated C3 |
| 2026-11-16 (before any main result) | C2 reuses C1's first answer (same model, same prompt, temperature 0) and adds only the retry | C1 and C2 then differ only by the intervention, which makes the paired McNemar comparison exact; halves compute |
| 2026-11-16 (before any main result) | `Qwen/Qwen3-8B` is also run, as a **supplementary** baseline outside the ten-model comparison (Qwen3.5-9B served, so it is the Alibaba entry) | Qwen3-8B is the probe and smoke-test model and the base of the Gananka models; its gap is the original research motivation. Reported separately, never ranked with the ten |
| 2026-11-16 (before any main result) | gpt-oss-20b has no non-reasoning mode: C1 and C2 use reasoning effort "low", C3 "high" | The closest equivalent of a plain answer; stated wherever gpt-oss C1 is reported |
| 2026-11-16 (load check, before any main result) | Added a **secondary** metric, *accuracy ignoring scale*: the checks pass and the digits equal the gold as displayed, whatever scale the model states. The headline accuracy is unchanged | In the Phi-4 load check 4 of 6 confident-wrong answers had the right digits but stated "scale: none". Those are genuine errors for any consumer of the value, but reporting them separately shows how much of a gap is reading the units header rather than finding the number |
| 2026-11-16 (smoke test, before any main result) | Error taxonomy: "scale or unit error" also covers a misplaced decimal point (the right digits times any power of ten, e.g. 273 for 2.73), and a right value restated in other units than the quoted line shows ("8,600" "in thousands" quoting "$8.6 million"), which had fallen into "wrong line quoted" | Seen in the smoke test; it had fallen into "wrong item", which misdescribes it |

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
