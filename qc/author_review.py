"""Build the author's independent review sheet for the frozen QC sample (PROTOCOL.md §11, round 4).

    python qc/author_review.py      # -> qc/author_review_v4.html (open it in a browser; no server needed)

The sheet shows each sampled question with its answer key, the pages the models saw and a link to the original
SEC filing. It deliberately leaves out the earlier verdicts in qc/handcheck_v4.jsonl, so this review is independent.
"Download verdicts" saves author_review_v4.jsonl; keep that file in qc/.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parent / "dataset"
SCALE = {0: "", 3: "thousands", 6: "millions", 9: "billions", -2: "percent"}


def period(p: dict) -> str:
    return p.get("instant") or f"{p.get('start')} to {p.get('end')}"


def build() -> list[dict]:
    ids = json.loads((HERE / "handcheck_sample_v4.json").read_text())["ids"]
    qs = {q["id"]: q for q in map(json.loads, (DATA / "questions.jsonl").open())}
    pages = {p["id"]: p for p in map(json.loads, (DATA / "pages.jsonl").open())}
    urls = {}
    for f in json.loads((DATA / "manifest.json").read_text())["filings"]:
        for doc in f["files"]["documents"]:
            urls[(f["accession"], doc["name"])] = doc["url"]
    items = []
    for n, i in enumerate(ids):
        q, g = qs[i], qs[i]["gold"]
        ev = (g.get("evidence") or [{}])[0]
        shown = sorted(q["pages"], key=lambda p: p != ev.get("page"))
        items.append({
            "n": n, "id": i, "slice": q["slice"], "company": q["company"], "form": q["form"],
            "question": q["question"], "found": g["status"] == "found", "display": g.get("display"),
            "scale": SCALE.get(g.get("scale"), str(g.get("scale"))), "unit": g.get("unit"),
            "period": period(g["period"]), "dims": g.get("dims") or {}, "line": ev.get("line"),
            "url": urls[(q["accession"], q["document"])],
            "pages": [{"label": pages[p]["page"], "gold": p == ev.get("page"), "text": pages[p]["text"]} for p in shown],
        })
    return items


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Filing-Evidence author review</title>
<style>
:root{--bg:#FAFAF7;--card:#fff;--ink:#12161C;--ink2:#3D4452;--muted:#5B6472;--line:#E3E5E0;--accent:#2E3F9E;--wash:#EEF0FA;--bad:#B3302A;--mark:#FFF1B8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 Inter,system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px}
.bar{max-width:980px;margin:auto;display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;justify-content:space-between}
.track{height:6px;background:var(--line);border-radius:3px;max-width:980px;margin:10px auto 0;overflow:hidden}.fill{height:100%;background:var(--accent);width:0}
main{max-width:980px;margin:auto;padding:20px 16px 64px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;margin-bottom:16px}
.meta{font-size:14px;color:var(--muted)}h1{font-size:22px;line-height:1.3;margin:6px 0 14px}dl{display:grid;grid-template-columns:130px minmax(0,1fr);gap:6px 12px;margin:0}dt{color:var(--muted)}dd{margin:0;overflow-wrap:anywhere}
.key{font-weight:600}code{font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--wash);padding:2px 5px;border-radius:4px}
button{font:inherit;font-weight:600;min-height:44px;padding:9px 14px;border:1px solid #C9CDC5;border-radius:8px;background:var(--card);color:var(--ink);cursor:pointer}button:hover{border-color:var(--accent)}button:focus-visible,a:focus-visible,textarea:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button.on{background:var(--accent);border-color:var(--accent);color:#fff}button.on.no{background:var(--bad);border-color:var(--bad)}.row{display:flex;flex-wrap:wrap;gap:10px}
textarea{width:100%;min-height:64px;margin-top:12px;padding:10px;font:inherit;border:1px solid #C9CDC5;border-radius:8px}
details{border-top:1px solid var(--line);padding:10px 0}summary{cursor:pointer;font-weight:600;min-height:32px}.pg{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:10px;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}.ln{white-space:pre-wrap;overflow-wrap:anywhere}.ln.hit{background:var(--mark);font-weight:700}
.nav{justify-content:space-between;margin-top:16px}
@media(max-width:600px){dl{grid-template-columns:minmax(0,1fr)}dt{margin-top:6px}}
</style></head><body>
<header><div class="bar"><strong id="pos"></strong><span id="done"></span><button id="dl">Download verdicts</button></div><div class="track"><div class="fill" id="fill"></div></div></header>
<main>
<section class="card"><div class="meta" id="meta"></div><h1 id="q"></h1><dl id="facts"></dl></section>
<section class="card"><strong id="ask"></strong><div class="row" id="choices" style="margin-top:12px"></div>
<textarea id="note" aria-label="Note" placeholder="Note (needed if it is not correct)"></textarea>
<div class="row nav"><button id="prev">Previous</button><button id="next">Next</button></div></section>
<section class="card"><strong>Pages the models saw</strong><div id="pages" style="margin-top:8px"></div></section>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const items=JSON.parse(document.getElementById('data').textContent),KEY='fe-author-review-v4',$=id=>document.getElementById(id);
let v={},i=0;try{v=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(v))}catch(e){}};
const norm=s=>(s||'').replace(/\s+/g,' ').trim();
const opts=x=>x.found?[['ok','Correct'],['value','Wrong answer key'],['unclear','Question unclear']]:[['ok','Correct: not on these pages'],['value','The answer is on these pages'],['unclear','Question unclear']];
function fact(k,t,c){const a=document.createElement('dt'),b=document.createElement('dd');a.textContent=k;b.textContent=t;if(c)b.className=c;$('facts').append(a,b)}
function show(){const x=items[i],r=v[x.id]||{};$('pos').textContent=`Question ${i+1} of ${items.length}`;const n=Object.keys(v).length;$('done').textContent=`${n} reviewed`;$('fill').style.width=(100*n/items.length)+'%';
$('meta').textContent=`${x.id} · ${x.slice} · ${x.company} · ${x.form}`;$('q').textContent=x.question;$('facts').replaceChildren();
if(x.found){fact('Answer key',[x.display,x.scale,x.unit].filter(Boolean).join(' '),'key');fact('Period',x.period);if(Object.keys(x.dims).length)fact('Segment',Object.values(x.dims).join(', '));fact('Line',x.line)}else fact('Answer key','Not found on the three pages shown','key');
const d=document.createElement('dt'),e=document.createElement('dd'),a=document.createElement('a');d.textContent='Source';a.href=x.url;a.target='_blank';a.rel='noopener';a.textContent='Open the original SEC filing';e.append(a);$('facts').append(d,e);
$('ask').textContent=x.found?'Do the page and filing support this exact answer to this question?':'Is the requested figure really absent from all three pages?';$('choices').replaceChildren(...opts(x).map(([k,l],j)=>{const b=document.createElement('button');b.textContent=`${j+1}. ${l}`;b.className=r.v===k?('on'+(k==='ok'?'':' no')):'';b.onclick=()=>pick(k);return b}));$('note').value=r.note||'';
$('pages').replaceChildren(...x.pages.map((p,j)=>{const o=document.createElement('details');o.open=j===0||!x.found;const s=document.createElement('summary');s.textContent=`Page ${p.label}${p.gold?' (answer page)':''}`;const b=document.createElement('div');b.className='pg';for(const t of p.text.split('\n')){const l=document.createElement('div');l.className='ln'+(p.gold&&norm(t).includes(norm(x.line))?' hit':'');l.textContent=t||' ';b.append(l)}o.append(s,b);return o}));$('prev').disabled=i===0;$('next').textContent=i===items.length-1?'Finish':'Next';scrollTo(0,0)}
function pick(k){const x=items[i];v[x.id]={v:k,note:$('note').value.trim()};save();show()}
$('note').oninput=()=>{const x=items[i];if(v[x.id]){v[x.id].note=$('note').value.trim();save()}};
$('prev').onclick=()=>{if(i>0){i--;show()}};$('next').onclick=()=>{if(i<items.length-1){i++;show()}};
$('dl').onclick=()=>{const rows=items.filter(x=>v[x.id]).map(x=>JSON.stringify({n:x.n,id:x.id,correct:v[x.id].v==='ok',gold_value_correct:v[x.id].v!=='value',failure_class:v[x.id].v==='ok'?null:v[x.id].v,note:v[x.id].note,reviewer:'author'}));const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([rows.join('\n')+'\n'],{type:'application/x-ndjson'}));a.download='author_review_v4.jsonl';a.click();URL.revokeObjectURL(a.href)};
addEventListener('keydown',e=>{if(e.target.tagName==='TEXTAREA')return;const o=opts(items[i]);if(['1','2','3'].includes(e.key))pick(o[+e.key-1][0]);if(e.key==='ArrowRight')$('next').click();if(e.key==='ArrowLeft')$('prev').click()});
show();
</script></body></html>
"""

if __name__ == "__main__":
    data = json.dumps(build(), ensure_ascii=False).replace("</", "<\\/")
    out = HERE / "author_review_v4.html"
    out.write_text(PAGE.replace("__DATA__", data), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
