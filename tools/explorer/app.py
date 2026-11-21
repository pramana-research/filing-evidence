"""Filing-Evidence Explorer: browse questions, answer keys, source pages and stored model answers; ask a model live;
record a manual review.

    uv run --extra explore python tools/explorer/app.py      # then open http://127.0.0.1:7860

See core.py for what is written where (never dataset/ or results/).
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="Filing-Evidence Explorer", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def dataset(key: str) -> core.DataSet:
    if key not in core.SETS:
        raise HTTPException(404, f"unknown set {key!r}")
    return core.SETS[key]


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/sets")
def sets():
    return [{"key": k, "title": d.title, "questions": len(d.qs), "companies": d.companies(),
             "reviewed": len(core.reviewed_ids(d))} for k, d in core.SETS.items()]  # fmt: skip


@app.get("/api/sets/{key}/questions")
def questions(
    key: str, company: str = "", form: str = "", slice: str = "", order: str = "id", search: str = ""
):
    d = dataset(key)
    reviewed = core.reviewed_ids(d)
    items = d.listing(company, form, slice, order, search)
    for it in items:
        it["reviewed"] = it["id"] in reviewed
    return items


@app.get("/api/sets/{key}/questions/{qid}")
def question(key: str, qid: str):
    det = dataset(key).detail(qid)
    if not det:
        raise HTTPException(404, "unknown question")
    return det


@app.get("/filing/{accession}")
def filing(accession: str):
    from fastapi.responses import HTMLResponse

    html = core.filing_html(accession)
    if html is None:
        raise HTTPException(404, "filing not stored locally")
    return HTMLResponse(html, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/models")
def models():
    return core.models()


@app.get("/api/server")
def server_status():
    return core.SERVER.status()


@app.post("/api/server/load")
def server_load(body: dict = Body(...)):  # noqa: B008
    names = {m["name"] for m in core.models()}
    if body.get("model") not in names:
        raise HTTPException(400, "unknown model")
    return core.SERVER.load(body["model"])


@app.post("/api/server/stop")
def server_stop():
    return core.SERVER.stop()


@app.post("/api/sets/{key}/questions/{qid}/ask")
def ask(key: str, qid: str, body: dict = Body(...)):  # noqa: B008
    dataset(key)
    return core.ask(key, qid, body.get("model", ""), body.get("setup", "C1"), body.get("prompt"))


@app.post("/api/sets/{key}/questions/{qid}/review")
def review(key: str, qid: str, body: dict = Body(...)):  # noqa: B008
    dataset(key)
    return core.save_review(key, qid, body)


def main() -> None:
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv(core.ROOT / ".env")  # EVAL_API_KEY (model server key), HF_TOKEN (model downloads)
    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="warning")


if __name__ == "__main__":
    main()
