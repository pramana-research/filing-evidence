
import pytest

from ixbrl import parse_number, read_document_set, read_filing, read_labels
from paths import data_dir

FILING = """<html><body>
<ix:header><ix:hidden>
  <ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" contextRef="I2026" unitRef="shares"
     decimals="-6" scale="6">8,000</ix:nonFraction>
</ix:hidden><ix:resources>
  <xbrli:context id="D2026"><xbrli:entity><xbrli:identifier>1</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-02-01</xbrli:startDate><xbrli:endDate>2026-01-31</xbrli:endDate></xbrli:period></xbrli:context>
  <xbrli:context id="D2025"><xbrli:entity><xbrli:identifier>1</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2024-02-01</xbrli:startDate><xbrli:endDate>2025-01-31</xbrli:endDate></xbrli:period></xbrli:context>
  <xbrli:context id="I2026"><xbrli:entity><xbrli:identifier>1</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2026-01-31</xbrli:instant></xbrli:period></xbrli:context>
  <xbrli:context id="D2026_club"><xbrli:entity><xbrli:identifier>1</xbrli:identifier>
    <xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">wmt:SamsClubMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
    <xbrli:period><xbrli:startDate>2025-02-01</xbrli:startDate><xbrli:endDate>2026-01-31</xbrli:endDate></xbrli:period></xbrli:context>
  <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
  <xbrli:unit id="shares"><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>
  <xbrli:unit id="usdPerShare"><xbrli:divide><xbrli:unitNumerator><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unitNumerator>
    <xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator></xbrli:divide></xbrli:unit>
</ix:resources></ix:header>
<div><p>Cover page</p></div>
<hr style="page-break-after:always"/>
<div><p>Consolidated Statements of Income</p>
<p>(Amounts in millions, except per share data)</p>
<table>
<tr><td>Total revenues</td><td>$</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="D2026" unitRef="usd"
   decimals="-6" scale="6" format="ixt:num-dot-decimal">713,163</ix:nonFraction></td>
   <td><ix:nonFraction name="us-gaap:Revenues" contextRef="D2025" unitRef="usd" decimals="-6" scale="6"
   format="ixt:num-dot-decimal">680,<span>985</span></ix:nonFraction></td></tr>
<tr><td>Net loss of subsidiary</td><td>(<ix:nonFraction name="us-gaap:ProfitLoss" contextRef="D2026" unitRef="usd"
   decimals="-6" scale="6" sign="-" format="ixt:num-dot-decimal">377</ix:nonFraction>)</td></tr>
<tr><td>Restructuring</td><td><ix:nonFraction name="us-gaap:RestructuringCharges" contextRef="D2026" unitRef="usd"
   scale="6" format="ixt:fixed-zero">—</ix:nonFraction></td></tr>
<tr><td>Diluted EPS</td><td><ix:nonFraction name="us-gaap:EarningsPerShareDiluted" contextRef="D2026"
   unitRef="usdPerShare" decimals="2" format="ixt:num-dot-decimal">2.73</ix:nonFraction></td></tr>
</table></div>
<div style="page-break-before:always"><p>Segments. Sam's Club U.S. operating income was
<ix:nonFraction name="us-gaap:OperatingIncomeLoss" contextRef="D2026_club" unitRef="usd" scale="9"
   decimals="-8" format="ixt:num-dot-decimal">2.5</ix:nonFraction> billion, and we had
<ix:nonFraction name="us-gaap:NumberOfStores" contextRef="I2026" unitRef="shares" scale="0"
   format="ixt-sec:numwordsen">three</ix:nonFraction> new clubs.</p>
<script>var x = "not rendered";</script></div>
</body></html>"""

LABELS = """<?xml version="1.0"?>
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink">
<link:labelLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">
  <link:loc xlink:type="locator" xlink:href="https://xbrl.fasb.org/us-gaap/2025/elts/us-gaap-2025.xsd#us-gaap_Revenues" xlink:label="loc_rev"/>
  <link:label xlink:type="resource" xlink:label="lab_rev" xlink:role="http://www.xbrl.org/2003/role/label">Revenues</link:label>
  <link:label xlink:type="resource" xlink:label="lab_rev" xlink:role="http://www.xbrl.org/2003/role/totalLabel">Total revenues</link:label>
  <link:labelArc xlink:type="arc" xlink:from="loc_rev" xlink:to="lab_rev"/>
</link:labelLink></link:linkbase>"""


@pytest.fixture(scope="module")
def filing():
    return read_filing(FILING)


def facts_by(filing, concept):
    return [f for f in filing.facts if f.concept == concept]


def test_pages_split_on_both_break_styles(filing):
    assert len(filing.pages) == 3
    assert filing.pages[0] == "Cover page"
    assert filing.pages[1].startswith("Consolidated Statements of Income")
    assert filing.pages[2].startswith("Segments.")
    assert "not rendered" not in "".join(filing.pages)          # <script> text never rendered


def test_hidden_facts_are_skipped(filing):
    assert not facts_by(filing, "dei:EntityCommonStockSharesOutstanding")
    assert filing.skipped["hidden"] == 1
    assert "8,000" not in "".join(filing.pages)


def test_values_scale_sign_and_formats(filing):
    rev = {f.context: f for f in facts_by(filing, "us-gaap:Revenues")}
    assert rev["D2026"].value == 713_163e6 and rev["D2026"].display == "713,163"
    assert rev["D2025"].value == 680_985e6 and rev["D2025"].display == "680,985"   # nested <span> inside the tag
    assert facts_by(filing, "us-gaap:ProfitLoss")[0].value == -377e6                # sign="-"
    assert facts_by(filing, "us-gaap:RestructuringCharges")[0].value == 0           # fixed-zero, displayed "—"
    assert facts_by(filing, "us-gaap:NumberOfStores")[0].value == 3                 # numwordsen
    seg = facts_by(filing, "us-gaap:OperatingIncomeLoss")[0]
    assert seg.value == pytest.approx(2.5e9) and seg.scale == 9


def test_units_contexts_and_dimensions(filing):
    eps = facts_by(filing, "us-gaap:EarningsPerShareDiluted")[0]
    assert eps.unit == "iso4217:USD/xbrli:shares" and eps.value == 2.73
    ctx = filing.contexts["D2026_club"]
    assert ctx.dims == {"us-gaap:StatementBusinessSegmentsAxis": "wmt:SamsClubMember"}
    assert (ctx.start, ctx.end) == ("2025-02-01", "2026-01-31")
    assert filing.contexts["I2026"].instant == "2026-01-31" and filing.contexts["I2026"].period_end == "2026-01-31"


def test_facts_are_located_on_their_page_and_line(filing):
    rev = {f.context: f for f in facts_by(filing, "us-gaap:Revenues")}
    occ = rev["D2026"].occurrences
    assert len(occ) == 1 and occ[0].page == 1
    assert occ[0].line == "Total revenues $ 713,163 680,985"               # table row: cells joined, collapsed
    assert occ[0].line in filing.pages[1].split("\n")
    seg = facts_by(filing, "us-gaap:OperatingIncomeLoss")[0].occurrences[0]
    assert seg.page == 2 and "operating income was 2.5 billion" in seg.line   # number inside prose


def test_parse_number_transforms():
    assert parse_number("1,234.5", "ixt:num-dot-decimal") == 1234.5
    assert parse_number("1.234,5", "ixt:num-comma-decimal") == 1234.5
    assert parse_number("—", "ixt:fixed-zero") == 0
    assert parse_number("none", "ixt-sec:numwordsen") == 0
    assert parse_number("n/a", None) is None


def test_read_labels():
    labels = read_labels(LABELS)
    assert labels["us-gaap:Revenues"] == {"label": "Revenues", "totalLabel": "Total revenues"}


WALMART = data_dir() / "finance" / "filings" / "WMT" / "0000104169-26-000055" / "wmt-20260131.htm"


@pytest.mark.skipif(not WALMART.exists(), reason="real filing not present (fetched by the benchmark)")
def test_real_walmart_10k():
    """Matches what a reader sees in the filing (and the 2026-11-15 probe)."""
    f = read_filing(WALMART.read_text(encoding="utf-8", errors="replace"))
    rev = [x for x in f.facts if x.concept == "us-gaap:Revenues" and not f.contexts[x.context].dims
           and f.contexts[x.context].end == "2026-01-31"]
    assert rev and rev[0].display == "713,163" and rev[0].value == 713_163e6
    lines = [o.line for o in rev[0].occurrences]
    assert "Total revenues 713,163 680,985 648,125" in lines
    page = rev[0].occurrences[0].page
    assert "Consolidated Statements of Income" in f.pages[page]
    assert len(f.facts) > 500 and len(f.pages) > 50


def test_document_set_shares_contexts_and_units():
    """Wells Fargo-style filing: contexts/units declared in the wrapper, facts displayed in the annual report."""
    wrapper = """<html><body><ix:header><ix:resources>
      <xbrli:context id="FY25"><xbrli:entity><xbrli:identifier>1</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
      </ix:resources></ix:header><p>Form 10-K cover</p></body></html>"""
    report = """<html><body><p>Consolidated Statement of Income</p><table><tr><td>Net income</td><td>
      <ix:nonFraction name="us-gaap:NetIncomeLoss" contextRef="FY25" unitRef="usd" scale="6">21,338</ix:nonFraction>
      </td></tr></table></body></html>"""
    out = read_document_set({"wrapper.htm": wrapper, "report.htm": report})
    assert out["wrapper.htm"].facts == []
    (fact,) = out["report.htm"].facts
    assert fact.value == 21_338e6 and fact.unit == "iso4217:USD"
    assert out["report.htm"].contexts["FY25"].end == "2025-12-31"
    alone = read_filing(report)                     # parsed alone, the context is unknown: fact skipped, not guessed
    assert alone.facts == [] and alone.skipped == {"unknown_context": 1}


def test_labels_embedded_in_schema():
    xsd = """<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:annotation><xs:appinfo>""" + \
        LABELS.split("?>", 1)[1] + "</xs:appinfo></xs:annotation></xs:schema>"
    assert read_labels(xsd)["us-gaap:Revenues"]["label"] == "Revenues"


def test_cells_wrapping_content_in_blocks_stay_on_one_row_line():
    """Many filers wrap every cell's content in <div>/<p>; the row must still render as one line."""
    html = """<html><body><ix:header><ix:resources>
      <xbrli:context id="C"><xbrli:entity><xbrli:identifier>1</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context>
      <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit></ix:resources></ix:header>
      <table><tr><td><div><p>Total assets</p></div></td><td><div>$</div></td>
      <td><p><ix:nonFraction name="us-gaap:Assets" contextRef="C" unitRef="usd" scale="6">619,003</ix:nonFraction></p></td>
      <td><p>512,163</p></td></tr>
      <tr><td><p>Total liabilities</p></td><td><p>243,686</p></td></tr></table>
      <div><p>After the table.</p></div></body></html>"""
    f = read_filing(html)
    assert f.facts[0].occurrences[0].line == "Total assets $ 619,003 512,163"
    assert f.pages[0].split("\n") == ["Total assets $ 619,003 512,163", "Total liabilities 243,686", "After the table."]


def test_long_pages_are_split_at_line_boundaries_and_facts_follow():
    """A document with no page-break markup (position-based layout) must not become one giant page."""
    import ixbrl
    rows = "".join(f"<p>Filler line number {i} with some words to take up space in the rendered text.</p>"
                   for i in range(400))
    html = """<html><body><ix:header><ix:resources>
      <xbrli:context id="C"><xbrli:entity><xbrli:identifier>1</xbrli:identifier></xbrli:entity>
        <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context>
      <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit></ix:resources></ix:header>""" + \
        rows + """<p>Total assets <ix:nonFraction name="us-gaap:Assets" contextRef="C" unitRef="usd">42</ix:nonFraction></p>
        </body></html>"""
    f = read_filing(html)
    assert f.split_pages == 1 and len(f.pages) > 1
    assert all(len(p) <= ixbrl.SPLIT_PAGE_CHARS for p in f.pages)
    occ = f.facts[0].occurrences[0]
    assert occ.page == len(f.pages) - 1 and occ.line == "Total assets 42" and occ.line in f.pages[occ.page]
    assert "\n".join(f.pages).count("Filler line number") == 400          # nothing lost or duplicated


def test_zero_width_characters_are_removed():
    html = "<html><body><table><tr><td>Repayments of debt&#8203;</td><td>(3,278,469)&#8203;</td></tr></table></body></html>"
    assert read_filing(html).pages[0] == "Repayments of debt (3,278,469)"
