"""Quick capability probe: can base Qwen3-8B extract numbers from a real 10-K with verifiable evidence?

Gold comes from the filing's own inline-XBRL tags (value, period, scale, location). Every quoted span is checked
against the page text by code. Throwaway script for a first look, not the v0.3 eval.

    python probe.py <filing.htm> <base_url> <served_model> <thinking:on|off> <out.json>
"""

import json
import random
import re
import sys
from html.parser import HTMLParser

import httpx

BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table"}


class Filing(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pages, self.buf = [], []
        self.facts, self.cur = [], None            # current ix:nonfraction
        self.contexts, self.ctx, self.ctx_field, self.in_segment = {}, None, None, False
        self.hidden = 0
        self._break_after = False

    def _newpage(self):
        self.pages.append("".join(self.buf)); self.buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        style = (a.get("style") or "").replace(" ", "").lower()
        if "page-break-before:always" in style or "break-before:page" in style:
            self._newpage()
        self._break_after = "page-break-after:always" in style or "break-after:page" in style
        if tag == "ix:header":
            self.hidden += 1
        if tag == "xbrli:context":
            self.ctx = {"id": a.get("id"), "dims": False}
        elif self.ctx is not None and tag in ("xbrli:startdate", "xbrli:enddate", "xbrli:instant"):
            self.ctx_field = tag.split(":")[1]
        elif self.ctx is not None and tag == "xbrli:segment":
            self.ctx["dims"] = True
        if tag == "ix:nonfraction" and not self.hidden:
            self.cur = {**a, "text": "", "page": len(self.pages), "offset": len("".join(self.buf))}
        if tag in BLOCK:
            self.buf.append("\n")
        elif tag == "td":
            self.buf.append("  ")
        if self._break_after and tag in ("hr", "br"):        # <hr style="page-break-after:always"/>
            self._newpage()

    def handle_endtag(self, tag):
        if tag == "ix:header":
            self.hidden -= 1
        if tag == "xbrli:context" and self.ctx:
            self.contexts[self.ctx["id"]] = self.ctx; self.ctx = None
        if tag in ("xbrli:startdate", "xbrli:enddate", "xbrli:instant"):
            self.ctx_field = None
        if tag == "ix:nonfraction" and self.cur is not None:
            self.facts.append(self.cur); self.cur = None
        if tag in BLOCK:
            self.buf.append("\n")
        style_end = None  # noqa: F841

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self.ctx is not None and self.ctx_field:
            self.ctx[self.ctx_field] = data.strip()
        if self.hidden:
            return
        self.buf.append(data)
        if self.cur is not None:
            self.cur["text"] += data

    def close(self):
        super().close(); self._newpage()


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def page_text(p: str) -> str:
    lines = [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in p.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def load(path):
    f = Filing(); f.feed(open(path, encoding="utf-8", errors="replace").read()); f.close()
    pages = [page_text(p) for p in f.pages]
    facts = []
    for x in f.facts:
        ctx = f.contexts.get(x.get("contextref"), {})
        if ctx.get("dims") or not x.get("text", "").strip():
            continue
        try:
            shown = float(x["text"].replace(",", "").strip() or "nan")
        except ValueError:
            continue
        scale = int(x.get("scale", "0"))
        val = shown * 10 ** scale * (-1 if x.get("sign") == "-" else 1)
        facts.append({"concept": x.get("name"), "value": val, "shown": x["text"].strip(), "scale": scale,
                      "page": x["page"], "end": ctx.get("enddate") or ctx.get("instant"),
                      "start": ctx.get("startdate")})
    return pages, facts


WANT = [  # (concept, label in plain words, kind)
    ("us-gaap:Revenues", "total revenues", "flow"),
    ("us-gaap:OperatingIncomeLoss", "operating income", "flow"),
    ("us-gaap:NetIncomeLoss", "consolidated net income attributable to Walmart", "flow"),
    ("us-gaap:ProfitLoss", "consolidated net income (including noncontrolling interest)", "flow"),
    ("us-gaap:EarningsPerShareDiluted", "diluted net income per share attributable to Walmart", "flow"),
    ("us-gaap:CashAndCashEquivalentsAtCarryingValue", "cash and cash equivalents", "stock"),
    ("us-gaap:Assets", "total assets", "stock"),
    ("us-gaap:LongTermDebtNoncurrent", "long-term debt (excluding amounts due within one year)", "stock"),
]


def fy_label(f):
    return f"the fiscal year ended {f['end']}" if f["start"] else f"{f['end']}"


def build(pages, facts, seed=0):
    rnd = random.Random(seed)
    items = []
    for concept, label, _kind in WANT:
        cands = [f for f in facts if f["concept"] == concept]
        if not cands:
            continue
        # one instance per period, on the page where the main statement shows it (first occurrence)
        by_end = {}
        for f in cands:
            by_end.setdefault(f["end"], f)
        for end in sorted(by_end, reverse=True)[:2]:              # current year + prior year (column trap)
            f = by_end[end]
            others = [i for i in range(len(pages)) if i != f["page"] and len(pages[i]) > 400]
            ctx_pages = sorted({f["page"], max(0, f["page"] - 1), rnd.choice(others)})
            items.append({"id": f"{concept.split(':')[1]}@{end}", "kind": "found", "label": label,
                          "period": fy_label(f), "gold": f, "pages": ctx_pages})
    # not-found traps
    ni = next(i for i in items if i["id"].startswith("NetIncomeLoss"))
    items.append({"id": "NetIncome@FY2019 (absent year)", "kind": "absent", "label": ni["label"],
                  "period": "the fiscal year ended 2019-01-31", "pages": ni["pages"]})
    rev = next(i for i in items if i["id"].startswith("Revenues"))
    items.append({"id": "R&D expense (Walmart doesn't report it)", "kind": "absent",
                  "label": "research and development expense", "period": rev["period"], "pages": rev["pages"]})
    items.append({"id": "Revenue Q3 (quarter not in a 10-K)", "kind": "absent", "label": "total revenues",
                  "period": "the third fiscal quarter ended 2025-10-31 (quarter only)", "pages": rev["pages"]})
    return items


SYSTEM = """You extract numbers from SEC filings. Use ONLY the pages provided. Reply with one JSON object and nothing else:
{"status": "found" or "not_found", "value": <number as shown, before applying any scale>, "scale": "<the units header that applies, e.g. 'in millions' or 'none'>", "page": <page number>, "span": "<the exact line from the page that contains the number, copied character for character>"}
If the item or the period is not on the provided pages, reply {"status": "not_found"}. Never use outside knowledge.
Example: {"status": "found", "value": 1234, "scale": "in millions", "page": 7, "span": "Total revenues $ 1,234 $ 1,100 $ 990"}"""


def prompt(item, pages):
    body = "\n\n".join(f"=== PAGE {p} ===\n{pages[p][:6000]}" for p in item["pages"])
    return f"{body}\n\nQuestion: What was Walmart's {item['label']} for {item['period']}?"


def ask(base, model, thinking, text):
    r = httpx.post(f"{base}/chat/completions", timeout=600, headers={"Authorization": "Bearer local"}, json={
        "model": model, "temperature": 0, "max_tokens": 6000 if thinking else 400,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
        "chat_template_kwargs": {"enable_thinking": thinking}})
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]["content"] or ""
    usage = r.json()["usage"]["completion_tokens"]
    return re.sub(r"<think>.*?(</think>|$)", "", msg, flags=re.S).strip(), usage


def grade(item, reply, pages):
    m = re.search(r"\{.*\}", reply, re.S)
    try:
        out = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        out = None
    if out is None:
        return {"verdict": "bad_format"}
    if item["kind"] == "absent":
        return {"verdict": "ok" if out.get("status") == "not_found" else "INVENTED", "out": out}
    if out.get("status") != "found":
        return {"verdict": "missed (said not_found)", "out": out}
    g = item["gold"]
    try:
        v = float(str(out.get("value")).replace(",", "").replace("$", ""))
    except ValueError:
        return {"verdict": "bad_value", "out": out}
    shown = float(g["shown"].replace(",", "")) * (-1 if g["value"] < 0 else 1)
    value_ok = abs(v - shown) < 1e-6 or abs(v - g["value"]) < max(1e-6, abs(g["value"]) * 1e-6)
    p = out.get("page")
    span = norm(str(out.get("span", "")))
    span_on_page = isinstance(p, int) and 0 <= p < len(pages) and span != "" and span in norm(pages[p])
    span_on_any = span != "" and any(span in norm(pages[q]) for q in item["pages"])
    num_in_span = g["shown"].replace(",", "") in span.replace(",", "")
    if value_ok and span_on_page and num_in_span:
        verdict = "ok"
    elif value_ok and not span_on_page:
        verdict = "right value, evidence not verifiable" + (" (wrong page)" if span_on_any else " (span not verbatim)")
    elif value_ok and span_on_page:
        verdict = "right value, quoted the wrong line"
    elif span_on_page and num_in_span:
        verdict = "CONFIDENT-WRONG (evidence checks out, value wrong)"
    elif span_on_page:
        verdict = "wrong value, real quote without that value (caught)"
    else:
        verdict = "wrong value, unverifiable quote"
    return {"verdict": verdict, "out": out, "gold": g["shown"], "gold_page": g["page"]}


def main():
    path, base, model, thinking, out_path = sys.argv[1:6]
    pages, facts = load(path)
    items = build(pages, facts)
    print(f"pages {len(pages)}, tagged facts {len(facts)}, questions {len(items)}", file=sys.stderr)
    results = []
    for it in items:
        reply, toks = ask(base, model, thinking == "on", prompt(it, pages))
        g = grade(it, reply, pages)
        results.append({"id": it["id"], "kind": it["kind"], "tokens": toks, **g, "reply": reply[:600]})
        print(f"{g['verdict'][:48]:48s} {toks:5d} tok  {it['id']}", file=sys.stderr)
    json.dump(results, open(out_path, "w"), indent=2, default=str)


if __name__ == "__main__":
    main()
