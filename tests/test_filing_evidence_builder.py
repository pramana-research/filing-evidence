"""Rules of the Filing-Evidence question builder (builder.py).

The page texts below are the real first lines of filings seen while calibrating (Apple, Microsoft, JPMorgan).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).parents[1] / "builder.py"
_spec = importlib.util.spec_from_file_location("fe_builder", _PATH)
B = importlib.util.module_from_spec(_spec)
sys.modules["fe_builder"] = B          # dataclasses look the module up while it loads
_spec.loader.exec_module(B)


@pytest.mark.parametrize("page", [
    "Apple Inc.\nCONSOLIDATED STATEMENTS OF OPERATIONS\n(In millions, except number of shares)\nYears Ended",
    "Apple Inc.\nCONSOLIDATED STATEMENTS OF CASH FLOWS\n(In millions)\nYears Ended",
    "PART II\nItem 8\nINCOME STATEMENTS\n(In millions, except per share amounts)\nYear Ended June 30,",
    "PART II\nItem 8\nCASH FLOWS STATEMENTS\n(In millions)",
    "JPMorgan Chase & Co.\nConsolidated balance sheets\nDecember 31, (in millions, except share data) 2025 2024",
    "The Travelers Companies, Inc.\nCONSOLIDATED STATEMENT OF INCOME (Unaudited)\n(in millions)",
    "Bank\nCONSOLIDATED STATEMENT OF FINANCIAL CONDITION\n(in millions)",
])
def test_statement_pages_detected(page):
    assert B.is_statement_page(page, usd_facts_on_page=20)


@pytest.mark.parametrize("page", [
    # a note that mentions a statement in its first sentence
    "Derivative Instruments\nThe Company presents derivative assets and liabilities at their gross fair values in the "
    "Consolidated Balance Sheets.\nIncome Taxes",
    # a table of contents / index of financial statements
    "Item 8. Financial Statements and Supplementary Data\nIndex to Consolidated Financial Statements Page\n"
    "Consolidated Statements of Operations for the years ended September 26, 2026 32",
    "Consolidated Statements of Operations 32\nConsolidated Balance Sheets 34",
    # equity statements are excluded (ambiguous component columns)
    "Apple Inc.\nCONSOLIDATED STATEMENTS OF SHAREHOLDERS’ EQUITY\n(In millions)",
    # accounting guidance heading that happens to contain "Income Statement"
    "PART II\nItem 8\nRecent Accounting Guidance Not Yet Adopted\n"
    "Income Statement – Disaggregation of Income Statement Expenses",
])
def test_non_statement_pages_rejected(page):
    assert not B.is_statement_page(page, usd_facts_on_page=20)


def test_statement_title_needs_real_figures():
    page = "Apple Inc.\nCONSOLIDATED BALANCE SHEETS\n(In millions)"
    assert B.is_statement_page(page, usd_facts_on_page=40)
    assert not B.is_statement_page(page, usd_facts_on_page=1)


def test_notes_range_ignores_running_item_headers_and_earlier_mentions():
    pages = [
        "Item 8\nIndex\nNotes to Consolidated Financial Statements 38",              # 0: index (before statements)
        "Apple Inc.\nCONSOLIDATED BALANCE SHEETS",                                      # 1: statement
        "PART II\nItem 8\nNOTES TO FINANCIAL STATEMENTS\nNOTE 1 — ACCOUNTING POLICIES",  # 2: notes start
        "PART II\nItem 8\nNOTE 2 — REVENUE",                                            # 3: running header, still notes
        "PART II\nItem 8\nREPORT OF INDEPENDENT REGISTERED PUBLIC ACCOUNTING FIRM",     # 4: closes the notes
        "Item 9. Changes in and Disagreements with Accountants",
    ]
    assert B.notes_range(pages, after=1) == range(2, 4)
    assert B.notes_range(pages, after=4) == range(0)


@pytest.mark.parametrize("start,end,instant,expected", [
    ("2025-07-01", "2025-09-30", None, "for the three months ended September 30, 2025"),
    ("2025-01-01", "2025-09-30", None, "for the nine months ended September 30, 2025"),
    ("2025-01-01", "2025-06-30", None, "for the six months ended June 30, 2025"),
    ("2025-02-01", "2026-01-31", None, "for the fiscal year ended January 31, 2026"),
    ("2024-09-29", "2025-09-27", None, "for the fiscal year ended September 27, 2025"),   # 52-week year
    (None, None, "2026-01-31", "as of January 31, 2026"),
    ("2025-01-01", "2025-03-15", None, None),                                             # non-standard length
])
def test_period_phrase(start, end, instant, expected):
    assert B.period_phrase(start, end, instant, "10-K") == expected


def test_date_helpers():
    assert B.quarter_start("2025-12-31") == "2025-10-01"
    assert B.quarter_start("2026-01-31") == "2025-11-01"
    assert B.shift_years("2025-12-31", 3) == "2022-12-31"
    assert B.shift_years("2024-02-29", 1) is None


def test_labels():
    labels = {"us-gaap:Revenues": {"label": "Revenues", "terseLabel": "Total revenues"},
              "wmt:SamsClubUSMember": {"label": "Sam's Club U.S. [Member]"},
              "us-gaap:EBITDA": {"label": "EBITDA"}}
    assert B.label_of(labels, "us-gaap:Revenues") == "total revenues"
    assert B.label_of(labels, "wmt:SamsClubUSMember") == "Sam's Club U.S."
    assert B.label_of(labels, "us-gaap:EBITDA") == "EBITDA"


@pytest.mark.parametrize("page", [
    "Table of Contents\nPart I — Financial Information\nItem 1. Financial Statements\nMetLife, Inc.\nInterim Condensed Consolidated Balance Sheets\nSeptember 30, 2026 and December 31, 2025 (Unaudited)",
    "Table of Contents\nMetLife, Inc.\nInterim Condensed Consolidated Statements of Operations and Comprehensive Income (Loss)",
    "Table of Contents\nSimon Property Group, Inc.\nUnaudited Consolidated Statements of Operations and Comprehensive Income",
    "Johnson & Johnson and subsidiaries consolidated balance sheets\nAt December 28, 2025 and December 29, 2024",
    "Consolidated Condensed Balance Sheets\nELI LILLY AND COMPANY\n(Dollars in millions)",
    "Table of Contents\nSTATEMENT 3 Caterpillar Inc.\nConsolidated Financial Position at December 31,\n(Dollars in millions)",
    "Table of Contents\nSTATEMENT 5 Caterpillar Inc.\nConsolidated Statement of Cash Flow for the Years Ended December 31,",
    "Table of Contents\nUNITED PARCEL SERVICE, INC. AND SUBSIDIARIES\nSTATEMENTS OF CONSOLIDATED INCOME\n(In millions)",
    "Consolidated Statement of Cash Flows Financial Table of Contents\nMillions of dollars",
    "FINANCIAL STATEMENTS\nDUKE ENERGY CORPORATION\nCONSOLIDATED BALANCE SHEETS\nDecember 31,",
])
def test_statement_title_styles_seen_in_filings(page):
    assert B.is_statement_page(page, usd_facts_on_page=50)


def test_note_pages_mentioning_a_statement_are_not_statements():
    page = ("Notes to the Consolidated Financial Statements Financial Table of Contents\nMillions of dollars\n"
            "Note 3\nInformation Relating to the Consolidated Statement of Cash Flows")
    assert not B.is_statement_page(page, usd_facts_on_page=100)
    page = "FINANCIAL STATEMENTS\nDUKE ENERGY CORPORATION\nCONSOLIDATED STATEMENTS OF CHANGES IN EQUITY"
    assert not B.is_statement_page(page, usd_facts_on_page=100)


@pytest.mark.parametrize("title", [
    "Notes to the Interim Condensed Consolidated Financial Statements (Unaudited) — (continued)",
    "Notes to Consolidated Condensed Financial Statements",
    "NOTES TO UNAUDITED CONSOLIDATED FINANCIAL STATEMENTS",
    "Index to Combined Notes to Condensed Consolidated Financial Statements",
    "NOTES TO CONSOLIDATED FINANCIAL STATEMENTS",
])
def test_notes_titles_seen_in_filings(title):
    pages = ["Apple Inc.\nCONSOLIDATED BALANCE SHEETS", f"Table of Contents\nCompany\n{title}\nNote 1", "Item 2. MD&A"]
    assert B.notes_range(pages, after=0) == range(1, 2)


def test_mdna_results_of_operations_is_not_a_statement():
    page = "Table of Contents\nConsolidated Results of Operations\nThe following discussion compares 2025 with 2024"
    assert not B.is_statement_page(page, usd_facts_on_page=30)


@pytest.mark.parametrize("line,expected", [
    ("Short-term borrowings (1) 18,323 2,704", "Short-term borrowings"),
    ("Total revenues 713,163 680,985 648,125", "Total revenues"),
    ("Interest expense 354 391 1,098 1,223", "Interest expense"),
    ("Less: Comprehensive income (loss) attributable to noncontrolling interest 1 (2) 2 (8)",
     "Less: Comprehensive income (loss) attributable to noncontrolling interest"),
    ("Net deferred tax liabilities $ 7,358 $ 5,271", "Net deferred tax liabilities"),
    ("Restructuring — (12)", None),            # one word
    ("2026 2025 2024", None),                  # a header row
])
def test_row_label(line, expected):
    assert B.row_label(line) == expected


def test_plain_label_rejects_inverted_taxonomy_style():
    labels = {"us-gaap:PremiumsWrittenNet": {"label": "Premiums Written, Net"},
              "us-gaap:InterestExpense": {"label": "Interest expense"}}
    assert B.plain_label(labels, "us-gaap:PremiumsWrittenNet") is None
    assert B.plain_label(labels, "us-gaap:InterestExpense") == "interest expense"


@pytest.mark.parametrize("line", [
    "Defined benefit pension and postretirement plans, net of tax of $(5), $1, $141 and $3 15 (2) (420) (6)",
    "Canceled/expired (0.3) 558.52",
])
def test_row_label_rejects_cut_or_one_word_labels(line):
    assert B.row_label(line) is None


def test_embedded_figures_are_not_column_figures():
    line = ("Pension and other postretirement benefit liability adjustments arising during the period "
            "(net of tax (provision) benefit of $1 and $(3)) 12 (8)")
    assert B.embedded_in_text(line, "1")
    assert not B.embedded_in_text("Total revenues 713,163 680,985 648,125", "680,985")


def test_label_must_match_the_evidence_line():
    sentence = ("As of December 31, 2025, the balance of borrowings outstanding under our commercial paper "
                "programs totaled $516.8 million")
    assert B.label_matches_line("commercial paper programs borrowings", sentence)
    assert not B.label_matches_line("liability balance", "Decommissioning obligations for divested assets $1.9 billion")
    assert not B.label_matches_line("revolving credit facilities and commercial paper", sentence)


@pytest.mark.parametrize("unit,label,hint", [
    ("xbrli:shares", "treasury stock, at cost", " (number of shares)"),
    ("xbrli:shares", "common shares outstanding", " (number)"),
    ("iso4217:USD/xbrli:shares", "diluted", " (per share)"),
    ("iso4217:USD/xbrli:shares", "diluted earnings per share", ""),
    ("xbrli:pure", "effective tax rate", ""),
    ("xbrli:pure", "return on average equity", " (%)"),
    ("iso4217:USD", "total revenues", ""),
])
def test_unit_hint(unit, label, hint):
    assert B.unit_hint(unit, label) == hint


# ---- regression tests from hand-check round 1 (qc/handcheck_v1.jsonl) -------------------------------------
from types import SimpleNamespace as NS  # noqa: E402


@pytest.mark.parametrize("line,expected", [
    ("Employee related obligations (Note 6) 6,559 6,957", "Employee related obligations"),                     # #10
    ("Unsecured short-term borrowings (includes $59,758 and $50,367 at fair value) 70,459 69,709",
     "Unsecured short-term borrowings"),                                                                    # #23
    ("Operating lease costs* $ 3,719 $ 3,447 $ 2,984", "Operating lease costs"),
    ("Cash dividends per share of common stock1 $ 0.70 $ 2.26 $ 5.46 $ 6.78", "Cash dividends per share of common stock"),
    ("Income (loss) before provision for income tax 3,000 1,210 5,542 3,544",
     "Income (loss) before provision for income tax"),                                                     # word-only parenthetical kept
])
def test_row_labels_after_round_1(line, expected):
    assert B.row_label(line) == expected


def test_clean_label_unit_suffixes():
    assert B.clean_label("Weighted-average shares outstanding (in shares)") == "Weighted-average shares outstanding"
    assert B.clean_label("Profit per common share (in dollars per share)") == "Profit per common share"


SCHEDULE_III = """SCHEDULE III — SUPPLEMENTARY INSURANCE INFORMATION
Year ended December 31, 2025:
Personal Lines $ 70,778 $ 46,662 $ 5,070 $ 11,252 $ 72,558
Commercial Lines 10,881 7,296 1,026 1,279 10,613
Other indemnity 2 1 0 22 3
Total $ 2,044 $ 43,310 $ 25,219 $ 0 $ 81,661 $ 3,549 $ 53,959 $ 6,096 $ 12,553 $ 83,174"""


def test_sparse_rows_detected():                                                                            # #53 #56 #59
    assert B.sparse_row(SCHEDULE_III, "Other indemnity 2 1 0 22 3")
    assert B.sparse_row(SCHEDULE_III, "Commercial Lines 10,881 7,296 1,026 1,279 10,613")
    balance = "Assets\nCash and cash equivalents $ 12,732 $ 10,828\nRestricted cash 632 660\nTotal assets 99,000 98,000"
    assert not B.sparse_row(balance, "Restricted cash 632 660")


INCOME = """U.S. Bancorp
Consolidated Statement of Income
Interest Expense
Deposits 2,491 2,648 7,105 7,700
Short-term borrowings 101 120 330 370"""


def test_multi_measure_row():                                                                               # #46
    line = "Exercisable at end of year 4,142,265 $ 143.68 4.3 years $ 606"
    ctx = NS(start=None, end=None, instant="2025-12-31", dims={})
    value = NS(concept="us-gaap:IntrinsicValue", context="c", occurrences=[NS(page=0, line=line)])
    price = NS(concept="us-gaap:ExercisePrice", context="c", occurrences=[NS(page=0, line=line)])
    doc = NS(contexts={"c": ctx}, by_line={(0, line): [value, price]})
    assert B.multi_measure_row(doc, value)


# ---- regression tests from hand-check rounds 1 and 2 (qc/handcheck_v1.jsonl, qc/handcheck_v2.jsonl) ----------

@pytest.mark.parametrize("line,expected", [
    ("Total gross unrecognized tax benefits as of May 31 $ 10,126 $ 9,438 $ 8,785", None),          # v2 #39
    ("Participating share-based awards — allocated income (13) (13) (41) (27)",
     "Participating share-based awards — allocated income"),                                       # v2 #42
    ("Balance at January 1, 2026 $ 683", None),                                                    # v2 #50
    ("Numerator – net income attributable to NEE $ 6,835 $ 6,946 $ 7,310",
     "net income attributable to NEE"),                     # prefix dropped after v3                                                # v2 #51
    ("Net balance as of January 1 33,067 33,315", None),                                           # v2 #54
    ("Purchases — — 33 14", None),                                                                  # one word
    ("-Accrued taxes (36) 206 23", "Accrued taxes"),                                                # leading dash
])
def test_row_labels_round_2(line, expected):
    assert B.row_label(line) == expected


def test_reliable_heading_finds_the_rows_block():                                                  # v1 #30 #43
    page = "U.S. Bancorp\nConsolidated Statement of Income\nInterest Expense\nDeposits 2,491 2,648 7,105 7,700"
    assert B.reliable_heading(page, "Deposits 2,491 2,648 7,105 7,700") == "Interest Expense"
    page = "Deferred tax assets\nAccrued liabilities (1,011) (1,199)"
    assert B.reliable_heading(page, "Accrued liabilities (1,011) (1,199)") == "Deferred tax assets"


def test_reliable_heading_stops_at_summary_rows():                                                 # v2 #14 #36
    spg = "\n".join([
        "BASIC AND DILUTED EARNINGS PER COMMON SHARE:",
        "Net income attributable to common stockholders $ 1.54 $ 1.86 $ 4.51 $ 4.83",
        "Consolidated Net Income $ 565,294 $ 702,696 $ 1,707,959 $ 1,824,237",
        "Unrealized gain (loss) on derivative hedge agreements 20,050 1,907 55,242 (30,521)",
        "Currency translation adjustments 60,728 (31,013) 51,367 (69,629)"])
    assert B.reliable_heading(spg, "Currency translation adjustments 60,728 (31,013) 51,367 (69,629)") is None
    nvda = "Operating expenses\nResearch and development 4,000 3,000\nOperating income 40,000 30,000\n" \
           "Income before income tax 45,000 33,000\nIncome tax expense 11,819 4,784"
    assert B.reliable_heading(nvda, "Income tax expense 11,819 4,784") is None


def test_captions_and_column_headers_are_not_headings():                                           # v2 #51 #43
    page = "(millions, except per share amounts)\nNumerator – net income attributable to NEE $ 6,835 $ 6,946"
    assert B.reliable_heading(page, page.split("\n")[1]) is None
    page = "Fiscal Year\nLess imputed interest 680"
    assert B.reliable_heading(page, page.split("\n")[1]) is None


@pytest.mark.parametrize("label,summary", [
    ("Total Assets", True), ("Net income", True), ("Consolidated net income", True),               # v2 #6 #27 #35
    ("Comprehensive income", True), ("Net investment income", True), ("Income before income taxes", True),
    ("Operating income", True), ("Cost of sales", False), ("Deposits", False), ("Net gain reclassified", False),
])
def test_summary_rows(label, summary):
    assert B.is_summary(label) == summary


def test_bare_totals():                                                                            # v2 #48
    assert not B.self_explanatory_total("Total deferred")
    assert B.self_explanatory_total("Total assets") and B.self_explanatory_total("Total current liabilities")


def test_labels_that_dont_stand_alone():                                                           # v2 #76, v1 #83
    assert not B.stands_alone("Duke Energy", on_statement=False, company="Duke Energy Corporation")
    assert not B.stands_alone("% of segment operating profit (loss)", on_statement=False, company="Lockheed")
    assert B.stands_alone("Cost of sales", on_statement=True, company="Walmart Inc.")
    assert not B.stands_alone("Accrued liabilities", on_statement=False, company="Walt Disney Company")


@pytest.mark.parametrize("label,ok", [
    ("Other Adjustments", False), ("acquisitions", False), ("write-offs", False),                  # v2 #53 #55 #56
    ("Total Assets", True), ("operating income", True), ("Policyholder Account Balance", True),
    ("Goodwill", True), ("revenues", True), ("Adjustments", False),
])
def test_specific_labels_for_segment_questions(label, ok):
    assert B.specific_label(label) == ok


def test_prose_label_must_match_the_numbers_sentence():                                            # v2 #68
    text = ("The Company remeasured its deferred income taxes balances following the law change. As a result, "
            "it recorded a one-time remeasurement cost of approximately $1.0 billion which increased the 2025 "
            "effective tax rate by approximately 3.6%.")
    sentence = B.sentence_with(text, "1.0")
    assert sentence.startswith("As a result")
    assert not B.label_matches_line("increase in deferred income taxes", sentence)


def test_period_needs_month_and_day_on_the_page():                                                 # v2 #87
    ctx = NS(start=None, end=None, instant="2024-01-28", dims={})
    fact = NS(context="c", occurrences=[NS(page=0, line="Shares outstanding at end of year 996 994 992")])
    hd = NS(contexts={"c": ctx}, pages=["Fiscal 2025 2024 2023\nShares outstanding at end of year 996 994 992"])
    assert not B.period_shown(hd, fact)
    ok = NS(contexts={"c": ctx}, pages=["January 28, 2024 and January 29, 2023\nShares outstanding 992 990"])
    assert B.period_shown(ok, fact)
    sep = NS(contexts={"c": NS(start=None, end=None, instant="2026-09-30", dims={})},
             pages=["(in millions) Sep 30, 2026 Dec 31, 2025\nGoodwill 24,963 24,967"])
    assert B.period_shown(sep, fact)


def test_sparse_rows_compare_only_within_their_own_table():
    """Two stacked tables: a 3-column period table, a heading, then a 6-column segment table. A full row of the
    narrow table is not sparse; a row with blank cells inside the wide table still is."""
    page = "\n".join([
        "Revenues by period",
        "Total revenues 713,163 680,985 648,125",
        "Operating income 29,825 29,348 27,012",
        "Revenues by segment",
        "Net sales 462,415 123,456 98,765 12,345 6,789 713,163",
        "Other income 1,234 567 — 89 1 1,891",
        "Impairments 22 (4)",
    ])
    assert not B.sparse_row(page, "Total revenues 713,163 680,985 648,125")
    assert not B.sparse_row(page, "Other income 1,234 567 — 89 1 1,891")
    assert B.sparse_row(page, "Impairments 22 (4)")
    assert B.sparse_row(SCHEDULE_III, "Other indemnity 2 1 0 22 3")                # still caught (round 1)


def test_segment_member_allows_the_operating_segments_marker():
    seg = "us-gaap:StatementBusinessSegmentsAxis"
    assert B.segment_member({seg: "gd:AerospaceMember"}) == "gd:AerospaceMember"
    assert B.segment_member({seg: "gd:AerospaceMember",
                             "us-gaap:ConsolidationItemsAxis": "us-gaap:OperatingSegmentsMember"}) == "gd:AerospaceMember"
    assert B.segment_member({seg: "gd:AerospaceMember",
                             "us-gaap:ConsolidationItemsAxis": "us-gaap:IntersegmentEliminationMember"}) is None
    assert B.segment_member({seg: "x:A", "srt:ProductOrServiceAxis": "x:Widgets"}) is None
    assert B.segment_member({"srt:StatementGeographicalAxis": "country:US"}) is None


# --- QC round 3 (qc/handcheck_v3.jsonl) ---------------------------------------------------------------------

def test_footnote_marker_after_a_parenthesis_is_removed():                                         # v3 #55
    assert B.clean_label("Other income (loss)1") == "Other income (loss)"
    assert B.row_label("Other income (loss)1 433 466 134 17 1,050 549 1,599") == "Other income (loss)"


def test_column_header_lines_and_eps_parts_are_not_headings():                                    # v3 #55 #85
    cvx = ("Upstream Downstream Segment Total All Other Total\n"
           "Sales and Other Operating Revenues 19,608 33,844 65,331 65,545 184,328 104 184,432\n"
           "Other income (loss)1 433 466 134 17 1,050 549 1,599")
    assert B.reliable_heading(cvx, cvx.split("\n")[2]) is None
    axp = ("Denominator: (b)\nBasic: Weighted-average common shares 673 692 678 697\n"
           "Basic EPS $ 5.43 $ 4.14 $ 14.24 $ 11.87\nDiluted EPS $ 5.42 $ 4.14 $ 14.22 $ 11.85")
    assert B.reliable_heading(axp, axp.split("\n")[3]) is None


def test_footnote_markers_are_removed_from_headings():                                            # v3 #86
    page = "Assumed health care cost trend rate (b)\nInitial trend 6.50 % 6.00 %\nUltimate trend 4.50 % 4.50 %"
    assert B.reliable_heading(page, page.split("\n")[2]) == "Assumed health care cost trend rate"


def test_sentence_fragments_are_not_row_labels():                                                 # v3 #79
    line = ("The number of the registrant’s Common Shares, $1.00 par value, outstanding as of January 31, 2026: "
            "585,906,353")
    assert B.row_label(line) is None


def test_prose_label_narrowed_by_its_sentence_is_dropped():                                       # v3 #70
    ups = ("Depreciation and amortization expense for property, plant and equipment during both of the nine "
           "months ended September 30, 2026 and 2025 was $2.3 billion.")
    assert B.qualified_in_sentence("Depreciation and amortization", ups)
    cat = "Amortization expense for the three and nine months ended September 30, 2026 was $21 million."
    assert not B.qualified_in_sentence("Amortization expense", cat)
    adbe = "Refund liabilities were $138 million and $137 million as of August 28, 2026 and November 28, 2025."
    assert not B.qualified_in_sentence("Refund liabilities", adbe)


def test_numerator_denominator_wording():                                                         # v3 rebuild scan
    assert B.row_label("Numerator – net income attributable to NEE $ 6,835 $ 6,946") == \
        "net income attributable to NEE"
    page = "EPS Denominator\nWeighted-average shares 5,690 5,670\nCommon-share equivalents 30 26"
    assert B.reliable_heading(page, page.split("\n")[2]) is None


def test_all_capitals_labels_are_lowered():                                                       # v3 #98
    assert B.sentence_case("COMPREHENSIVE INCOME") == "comprehensive income"
    assert B.sentence_case("NET INCOME ATTRIBUTABLE TO NEE") == "net income attributable to NEE"
    assert B.sentence_case("Sam's Club U.S.") == "Sam's Club U.S."
