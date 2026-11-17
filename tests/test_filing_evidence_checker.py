"""The Filing-Evidence checker (research/benchmarks/filing-evidence/checker.py): PROTOCOL §7-§8 on hand-made
questions shaped like the dataset's."""

import importlib.util
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).parents[1] / "research" / "benchmarks" / "filing-evidence"
_spec = importlib.util.spec_from_file_location("fe_checker", _DIR / "checker.py")
C = importlib.util.module_from_spec(_spec)
sys.modules["fe_checker"] = C
_spec.loader.exec_module(C)

PAGES = {
    "a/x.htm#p4": "CONSOLIDATED BALANCE SHEETS\n(In millions)\nTotal liabilities 275,746 285,508\nTotal equity 70,000 66,000",
    "a/x.htm#p3": "CONSOLIDATED STATEMENTS OF INCOME\nNet income $ 29,789 $ 23,434\nDiluted EPS $ 2.01 $ 1.57",
    "a/x.htm#p19": "Note 9\nWeighted-average discount rate 4.09 % 3.96 %\nPayments (6,716) (5,100)",
}


def q(gold, slice_="S1"):
    return {"id": "FE-T", "slice": slice_, "pages": list(PAGES), "page_labels": [4, 3, 19], "gold": gold}


LIAB = {"status": "found", "display": "275,746", "shown_value": 275746.0, "scale": 6, "unit": "USD",
        "value": 275746e6, "evidence": [{"page": "a/x.htm#p4", "line": "Total liabilities 275,746 285,508"}]}
EPS = {"status": "found", "display": "2.01", "shown_value": 2.01, "scale": 0, "unit": "USD per share",
       "value": 2.01, "evidence": [{"page": "a/x.htm#p3", "line": "Diluted EPS $ 2.01 $ 1.57"}]}
RATE = {"status": "found", "display": "3.96", "shown_value": 3.96, "scale": -2, "unit": "pure",
        "value": 0.0396, "evidence": [{"page": "a/x.htm#p19", "line": "Weighted-average discount rate 4.09 % 3.96 %"}]}
PAY = {"status": "found", "display": "6,716", "shown_value": 6716.0, "scale": 6, "unit": "USD",
       "value": 6716e6, "evidence": [{"page": "a/x.htm#p19", "line": "Payments (6,716) (5,100)"}]}
ABSENT = {"status": "not_found"}


def reply(**kw):
    import json
    return json.dumps({"status": "found", **kw})


def test_correct_with_scale_and_display_formats():
    r = C.check(reply(value=275746, scale="in millions", page=4, span="Total liabilities 275,746 285,508"), q(LIAB), PAGES)
    assert (r.outcome, r.category) == ("correct", None)
    r = C.check(reply(value="275,746", scale="In millions", page="4", span="Total liabilities  275,746 285,508"),
                q(LIAB), PAGES)
    assert r.outcome == "correct"                      # string number, string page, whitespace normalised


def test_sign_not_graded():
    r = C.check(reply(value=-6716, scale="in millions", page=19, span="Payments (6,716) (5,100)"), q(PAY), PAGES)
    assert r.outcome == "correct"
    r = C.check(reply(value=6716, scale="millions", page=19, span="Payments (6,716) (5,100)"), q(PAY), PAGES)
    assert r.outcome == "correct"


def test_per_share_and_percent_compared_as_displayed():
    r = C.check(reply(value=2.01, scale="in millions, except per share", page=3, span="Diluted EPS $ 2.01 $ 1.57"),
                q(EPS, "S7"), PAGES)
    assert r.outcome == "correct"
    r = C.check(reply(value="3.96%", scale="none", page=19, span="Weighted-average discount rate 4.09 % 3.96 %"),
                q(RATE, "S7"), PAGES)
    assert r.outcome == "correct"


def test_confident_wrong_column_and_scale():
    r = C.check(reply(value=285508, scale="in millions", page=4, span="Total liabilities 275,746 285,508"), q(LIAB), PAGES)
    assert (r.outcome, r.category) == ("confident_wrong", "wrong_period_or_column")
    r = C.check(reply(value=275746, scale="in thousands", page=4, span="Total liabilities 275,746 285,508"),
                q(LIAB), PAGES)
    assert (r.outcome, r.category) == ("confident_wrong", "scale_or_unit")
    r = C.check(reply(value=70000, scale="in millions", page=4, span="Total equity 70,000 66,000"), q(LIAB), PAGES)
    assert (r.outcome, r.category) == ("confident_wrong", "wrong_item")


def test_unverifiable_right():
    r = C.check(reply(value=275746, scale="in millions", page=3, span="Total liabilities 275,746 285,508"), q(LIAB), PAGES)
    assert (r.outcome, r.failed_check, r.category) == ("unverifiable_right", "span", "wrong_page_cited")
    r = C.check(reply(value=275746, scale="in millions", page=7, span="Total liabilities 275,746 285,508"), q(LIAB), PAGES)
    assert (r.outcome, r.failed_check, r.category) == ("unverifiable_right", "page", "wrong_page_cited")
    r = C.check(reply(value=275746, scale="in millions", page=4, span="Total liabilities $275,746"), q(LIAB), PAGES)
    assert (r.outcome, r.category) == ("unverifiable_right", "span_not_verbatim")
    r = C.check(reply(value=275746, scale="in millions", page=4, span="Total equity 70,000 66,000"), q(LIAB), PAGES)
    assert (r.outcome, r.failed_check, r.category) == ("unverifiable_right", "value", "wrong_line_quoted")


def test_caught_wrong_uses_the_answered_value():
    # the probe's grader checked the gold value against the quote; the checker tests the answered value
    r = C.check(reply(value=273, scale="in millions", page=3, span="Diluted EPS $ 2.01 $ 1.57"), q(EPS, "S7"), PAGES)
    assert (r.outcome, r.failed_check) == ("caught_wrong", "value")


def test_not_found_paths_and_invalid():
    assert C.check('{"status": "not_found"}', q(ABSENT, "S8"), PAGES).outcome == "abstained_correctly"
    r = C.check(reply(value=29789, scale="in millions", page=3, span="Net income $ 29,789 $ 23,434"), q(ABSENT, "S8"),
                PAGES)
    assert (r.outcome, r.category) == ("invented", "invented_on_s8")
    assert C.check('{"status": "not_found"}', q(LIAB), PAGES).outcome == "missed"
    assert C.check("The answer is 275,746.", q(LIAB), PAGES).outcome == "invalid"
    assert C.check('{"status": "found", "value": "n/a"}', q(LIAB), PAGES).outcome == "invalid"


def test_parse_reply_tolerates_wrappers():
    txt = '<think>maybe {"status": "x"</think>```json\n{"status": "not_found"}\n```'
    assert C.parse_reply(txt) == {"status": "not_found"}
    assert C.parse_reply('Sure! {"note": 1} then {"status": "found", "value": 1}')["value"] == 1


def test_retry_message_names_the_check_not_the_answer(tmp_path):
    t = C.load_retry_templates(_DIR / "prompts" / "v1_retry.txt")
    msg = C.retry_message("page", {"page": 7}, q(LIAB), t)
    assert "Page 7 is not one of the provided pages (3, 4, 19)" in msg and "275" not in msg
    assert set(t) == {"parse", "page", "span", "value", "footer"}


@pytest.mark.parametrize("k,n,lo,hi", [(98, 100, 0.9300, 0.9945), (0, 10, 0.0, 0.2775), (5, 10, 0.2366, 0.7634)])
def test_wilson(k, n, lo, hi):
    a, b = C.wilson(k, n)
    assert a == pytest.approx(lo, abs=1e-3) and b == pytest.approx(hi, abs=1e-3)


def test_summarize():
    rows = [
        {"slice": "S1", "outcome": "correct", "category": None, "retried": False, "completion_tokens": 50, "seconds": 1},
        {"slice": "S1", "outcome": "confident_wrong", "category": "wrong_item", "retried": True,
         "completion_tokens": 60, "seconds": 2},
        {"slice": "S8", "outcome": "abstained_correctly", "category": None, "retried": False,
         "completion_tokens": 10, "seconds": 1},
    ]
    s = C.summarize(rows)
    assert s["accuracy"]["k"] == 1 and s["accuracy"]["n"] == 2
    assert s["confident_wrong"]["k"] == 1 and s["confident_wrong"]["n"] == 3
    assert s["abstention_accuracy"]["rate"] == 1.0 and s["retry_rate"]["k"] == 1


def test_dropped_decimal_point_is_a_scale_error():                                               # smoke SMOKE-09
    r = C.check(reply(value=273, scale="none", page=3, span="Diluted EPS $ 2.01 $ 1.57"),
                q({**EPS, "display": "2.73", "shown_value": 2.73, "value": 2.73}, "S7"), PAGES)
    assert (r.outcome, r.category) == ("caught_wrong", "scale_or_unit")


def test_right_ignoring_scale_is_secondary():                                                    # phi-4 load check
    r = C.check(reply(value=275746, scale="none", page=4, span="Total liabilities 275,746 285,508"), q(LIAB), PAGES)
    assert (r.outcome, r.category, r.right_ignoring_scale) == ("confident_wrong", "scale_or_unit", True)
    r = C.check(reply(value=285508, scale="none", page=4, span="Total liabilities 275,746 285,508"), q(LIAB), PAGES)
    assert r.right_ignoring_scale is False
    rows = [{"slice": "S1", "outcome": "confident_wrong", "category": "scale_or_unit", "right_ignoring_scale": True,
             "retried": False, "completion_tokens": 5, "seconds": 1}]
    assert C.summarize(rows)["accuracy_ignoring_scale"]["k"] == 1


def test_value_restated_in_other_units_is_a_scale_issue():                                       # ministral load check
    r = C.check(reply(value=275746000, scale="in thousands", page=4, span="Total liabilities 275,746 285,508"),
                q(LIAB), PAGES)
    assert (r.outcome, r.failed_check, r.category) == ("unverifiable_right", "value", "scale_or_unit")
