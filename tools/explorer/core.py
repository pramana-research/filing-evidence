"""Data, model server and live-run logic of the Filing-Evidence Explorer (the web layer is app.py).

Nothing here writes to dataset/ or results/. Live answers go to review/live/, manual reviews to
review/<set>/review.jsonl. Live answers are graded with the benchmark's own checker (checker.py) and the model is
served with the benchmark's pinned command (serve.command), so a live answer is directly comparable with a stored
one, but it is not a benchmark result.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import checker  # noqa: E402
import runner  # noqa: E402
import serve  # noqa: E402

PORT = 8000
BASE = f"http://127.0.0.1:{PORT}/v1"
LOCK = ROOT / "results" / ".gpu.lock"
REVIEW = ROOT / "review"
LIVE = REVIEW / "live"
LOGS = ROOT / "logs"

SCALE_WORDS = {9: "billions", 6: "millions", 3: "thousands", 0: "as shown", -2: "percent"}
MODEL_ORDER = ["qwen3.5-9b", "gpt-oss-20b", "granite-4.2-8b", "glm-4.6v-flash", "ministral-3-8b", "gemma-3-12b",
               "llama-3.1-8b", "phi-4", "nemotron-nano-9b-v2", "olmo-3-7b", "qwen3-8b"]  # fmt: skip
CHECK_STEPS = [("parse", "Answer parses as JSON"), ("page", "Cited page was shown"),
               ("span", "Quote is verbatim on that page"), ("value", "Answered value is in the quote")]  # fmt: skip


def venv_with_vllm() -> Path:
    if os.environ.get("VLLM_VENV"):
        return Path(os.environ["VLLM_VENV"])
    for cand in (ROOT / ".venv", ROOT.parent / "forge" / ".venv"):
        if (cand / "bin" / "vllm").exists():
            return cand
    return ROOT / ".venv"


VLLM_VENV = venv_with_vllm()


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------- data


class DataSet:
    """One question set with its pages and any stored benchmark answers."""

    def __init__(self, key: str, title: str, data_dir: Path, results_dir: Path):
        self.key, self.title = key, title
        self.qs = [json.loads(line) for line in (data_dir / "questions.jsonl").open()]
        self.by_id = {q["id"]: q for q in self.qs}
        self.order = {q["id"]: i for i, q in enumerate(self.qs)}
        self.pages = {p["id"]: p["text"] for p in map(json.loads, (data_dir / "pages.jsonl").open())}
        self.answers: dict[str, dict[tuple[str, str], dict]] = defaultdict(dict)
        if results_dir.exists():
            for f in results_dir.glob("*/*/answers.jsonl"):
                model, setup = f.parent.parent.name, f.parent.name
                if setup not in ("C1", "C2", "C3"):
                    continue  # load checks such as C1-limit24
                for line in f.open():
                    r = json.loads(line)
                    self.answers[r["id"]][(model, setup)] = r
        self.cik: dict[str, int] = {}
        man = data_dir / "manifest.json"
        if man.exists():
            for f in json.loads(man.read_text()).get("filings", []):
                self.cik[f["accession"]] = f["cik"]

    def score(self, qid: str) -> tuple[int, int]:
        rows = [r for (_, s), r in self.answers[qid].items() if s == "C1"]
        return sum(r["outcome"] in ("correct", "abstained_correctly") for r in rows), len(rows)

    def edgar_url(self, q: dict) -> str | None:
        cik = self.cik.get(q["accession"])
        if not cik:
            return None
        return (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{q['accession'].replace('-', '')}/{q['document']}"
        )

    def companies(self) -> list[dict]:
        seen = Counter(q["ticker"] for q in self.qs)
        names = {q["ticker"]: q["company"] for q in self.qs}
        return [{"ticker": t, "company": names[t], "questions": seen[t]} for t in sorted(names)]

    def listing(
        self, company: str = "", form: str = "", slc: str = "", order: str = "id", search: str = ""
    ) -> list[dict]:
        qs = self.qs
        if company:
            qs = [q for q in qs if q["ticker"] == company]
        if form:
            qs = [q for q in qs if q["form"] == form]
        if slc:
            qs = [q for q in qs if q["slice"] == slc]
        if search:
            s = search.lower()
            qs = [q for q in qs if s in q["question"].lower() or s in q["id"].lower()]
        out = []
        for q in qs:
            ok, n = self.score(q["id"])
            outcomes = [r["outcome"] for r in self.answers[q["id"]].values()]
            item = {"id": q["id"], "slice": q["slice"], "form": q["form"], "ticker": q["ticker"],
                    "company": q["company"], "question": q["question"], "ok": ok, "n": n,
                    "wrong_passed": any(o in ("confident_wrong", "invented") for o in outcomes)}  # fmt: skip
            out.append(item)
        if order == "wrong_passed":
            out = [x for x in out if x["wrong_passed"]]
        if order in ("hardest", "wrong_passed"):
            out.sort(key=lambda x: (x["ok"] / x["n"] if x["n"] else 1, self.order[x["id"]]))
        return out

    def detail(self, qid: str) -> dict | None:
        q = self.by_id.get(qid)
        if not q:
            return None
        g = q["gold"]
        labels = dict(zip(q["pages"], q["page_labels"], strict=True))
        gold: dict = {"status": g["status"]}
        ev_page = ev_line = None
        if g["status"] == "found":
            ev_page, ev_line = g["evidence"][0]["page"], g["evidence"][0]["line"]
            gold.update({
                "display": g["display"], "value": g["value"], "scale": g["scale"],
                "scale_words": SCALE_WORDS.get(g["scale"], str(g["scale"])), "unit": g["unit"],
                "negative": g["negative"], "period": g["period"], "concept": g["concept"], "label": g["label"],
                "dims": [{"axis": k.split(":")[-1], "member": v.split(":")[-1]} for k, v in g["dims"].items()],
                "evidence_page": labels.get(ev_page), "evidence_line": ev_line,
                "fact_index": int(g["fact_id"][1:]) if g.get("fact_id", "").startswith("f") else None,
            })  # fmt: skip
        pages = []
        for pid, label in zip(q["pages"], q["page_labels"], strict=True):
            text = self.pages.get(pid, "")
            hl = None
            if pid == ev_page:
                for i, line in enumerate(text.split("\n")):
                    if checker.norm_ws(line) == checker.norm_ws(ev_line):
                        hl = i
                        break
            pages.append({"label": label, "text": text, "is_answer": pid == ev_page, "highlight_line": hl})
        answers = []
        rank = {m: i for i, m in enumerate(MODEL_ORDER)}
        for (m, s), r in sorted(self.answers[qid].items(), key=lambda kv: (rank.get(kv[0][0], 99), kv[0][1])):
            a = r.get("answer") or {}
            last = (r.get("attempts") or [{}])[-1]
            answers.append({
                "model": m, "setup": s, "outcome": r["outcome"], "category": r.get("category"),
                "failed_check": r.get("failed_check"), "status": a.get("status"), "value": a.get("value"),
                "scale": a.get("scale"), "page": a.get("page"), "span": a.get("span"), "retried": r.get("retried"),
                "tokens": r.get("completion_tokens"), "seconds": r.get("seconds"),
                "raw": last.get("content"), "reasoning": (last.get("reasoning") or "")[:20000],
            })  # fmt: skip
        ok, n = self.score(qid)
        return {
            "id": q["id"], "set": self.key, "question": q["question"], "company": q["company"], "ticker": q["ticker"],
            "form": q["form"], "slice": q["slice"], "subtype": q.get("subtype"), "report_date": q["report_date"],
            "edgar": self.edgar_url(q), "accession": q["accession"], "gold": gold, "pages": pages, "answers": answers,
            "score": {"ok": ok, "n": n}, "prompt": runner.render(runner.PROMPT.read_text(), q, self.pages),
            "review": load_review(self, qid),
        }  # fmt: skip


FILINGS: dict[str, Path | None] = {}  # accession -> local path of the primary document (looked up once)


def filing_path(accession: str) -> Path | None:
    """The locally stored primary document of a filing in the question sets
    (DATA_DIR/finance/filings/<ticker>/<accession>/<document>). Only accessions used by a question are served."""
    if accession in FILINGS:
        return FILINGS[accession]
    q = next((q for ds in SETS.values() for q in ds.qs if q["accession"] == accession), None)
    found = None
    if q:
        import paths

        cand = paths.data_dir() / "finance" / "filings" / q["ticker"] / accession / q["document"]
        found = cand if cand.is_file() else None
    FILINGS[accession] = found
    return found


def filing_html(accession: str) -> str | None:
    """The original filing HTML with the locator script injected (highlights a tagged fact or a quoted line)."""
    p = filing_path(accession)
    if not p:
        return None
    html = p.read_text(errors="replace")
    inject = '<link rel="stylesheet" href="/static/locator.css"><script src="/static/locator.js"></script>'
    i = html.lower().rfind("</body>")
    return html[:i] + inject + html[i:] if i >= 0 else html + inject


def load_sets() -> dict[str, DataSet]:
    sets = {
        "main": DataSet("main", "Filing-Evidence v1 (frozen)", ROOT / "dataset", ROOT / "results" / "main")
    }
    sect = ROOT / "sets" / "sectors"
    if (sect / "dataset" / "questions.jsonl").exists():
        sets["sectors"] = DataSet("sectors", "Filing-Evidence Sectors", sect / "dataset", sect / "results")
    return sets


SETS = load_sets()


def models() -> list[dict]:
    cfg = yaml.safe_load((ROOT / "models.yaml").read_text())["models"]
    rank = {m: i for i, m in enumerate(MODEL_ORDER)}
    out = []
    for name, m in sorted(cfg.items(), key=lambda kv: rank.get(kv[0], 99)):
        out.append({"name": name, "repo": m["repo"], "company": m.get("company"), "precision": m.get("precision"),
                    "thinking": (m.get("request") or {}).get("C3") is not None,
                    "supplementary": name == "qwen3-8b"})  # fmt: skip
    return out


# ---------------------------------------------------------------- model server


class Server:
    """One vLLM server at a time on :8000, started in a background thread with the benchmark's pinned command,
    holding the same GPU lock as run_all.sh."""

    def __init__(self):
        self.mu = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.cmd: list[str] = []
        self.lockf = None
        self.state = {"state": "idle", "model": None, "message": "No model loaded", "since": None}

    @staticmethod
    def key() -> str:
        return os.environ.get("EVAL_API_KEY", "local")

    def served(self) -> str | None:
        try:
            r = httpx.get(f"{BASE}/models", headers={"Authorization": f"Bearer {self.key()}"}, timeout=2)
            data = r.json().get("data") or []
            return data[0]["id"] if data else None
        except Exception:
            return None

    def revision(self) -> str | None:
        return next((self.cmd[i + 1] for i, c in enumerate(self.cmd) if c == "--revision"), None)

    def status(self) -> dict:
        st = dict(self.state)
        if st["state"] == "loading":
            st["elapsed"] = int(time.time() - st["since"])
            return st
        s = self.served()
        if s:
            owned = self.proc is not None and self.proc.poll() is None
            return {"state": "ready", "model": s, "owned": owned,
                    "message": f"{s} is ready" + ("" if owned else " (started outside this session)")}  # fmt: skip
        if st["state"] == "ready":  # it was ready but no longer answers
            st = {"state": "idle", "model": None, "message": "No model loaded", "since": None}
            self.state = st
        return st

    def load(self, name: str) -> dict:
        with self.mu:
            if self.state["state"] == "loading":
                return self.status()
            self.state = {
                "state": "loading",
                "model": name,
                "message": f"Loading {name}",
                "since": time.time(),
            }
        threading.Thread(target=self._load, args=(name,), daemon=True).start()
        return self.status()

    def _set(self, state: str, model: str | None, message: str):
        self.state = {"state": state, "model": model, "message": message, "since": None}

    def _load(self, name: str):
        current = self.served()
        if current == name:
            self._set("ready", name, f"{name} is ready")
            return
        if current:
            self._kill_server()
        if self.lockf is None:
            LOCK.parent.mkdir(parents=True, exist_ok=True)
            f = open(LOCK, "w")  # noqa: SIM115 (held for the server's lifetime)
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                f.close()
                self._set("error", name, "The GPU is busy: a benchmark run holds the GPU lock.")
                return
            self.lockf = f
        cmd = serve.command(name)
        cmd[0] = str(VLLM_VENV / "bin" / "vllm")
        env = {**os.environ, "PATH": f"{VLLM_VENV / 'bin'}:{os.environ.get('PATH', '')}",
               "VLLM_USE_FLASHINFER_SAMPLER": "0"}  # fmt: skip
        LOGS.mkdir(exist_ok=True)
        log = LOGS / f"explorer-serve-{name}.log"
        self.cmd = cmd
        with log.open("w") as out:
            self.proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, env=env, cwd=ROOT,
                                         start_new_session=True)  # fmt: skip
        t0 = time.time()
        while time.time() - t0 < 1800:
            if self.proc.poll() is not None:
                tail = [ln for ln in log.read_text().splitlines() if "Error" in ln or "error" in ln][-3:]
                self._release()
                self._set(
                    "error", name, "The model failed to start. " + (" ".join(tail)[:400] or f"See {log}")
                )
                return
            if self.served() == name:
                self._set("ready", name, f"{name} is ready (loaded in {int(time.time() - t0)} s)")
                return
            time.sleep(3)
        self._kill_server()
        self._set("error", name, "Gave up after 30 minutes.")

    def stop(self) -> dict:
        with self.mu:
            if self.state["state"] == "loading":
                return self.status()
            self._kill_server()
            self._set("idle", None, "No model loaded")
        return self.status()

    def _kill_server(self):
        pids = []
        if self.proc and self.proc.poll() is None:
            pids.append(self.proc.pid)
        else:  # a server started by an earlier Explorer session: find it by its command line
            out = subprocess.run(
                ["pgrep", "-f", f"vllm serve .*--port {PORT}"], capture_output=True, text=True
            )
            pids = [int(p) for p in out.stdout.split()]
        for pid in pids:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        t0 = time.time()
        while self.served() and time.time() - t0 < 90:
            time.sleep(2)
        for pid in pids:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(3)  # let the GPU memory free
        self._release()

    def _release(self):
        self.proc = None
        if self.lockf is not None:
            fcntl.flock(self.lockf, fcntl.LOCK_UN)
            self.lockf.close()
            self.lockf = None


SERVER = Server()


# ---------------------------------------------------------------- live run


def ask(set_key: str, qid: str, model: str, setup: str, prompt: str | None) -> dict:
    ds = SETS[set_key]
    q = ds.by_id.get(qid)
    if not q:
        return {"error": "Unknown question."}
    if SERVER.served() != model:
        return {"error": f"Load {model} first."}
    info = next((m for m in models() if m["name"] == model), None)
    if setup == "C3" and not (info and info["thinking"]):
        return {"error": f"{model} has no thinking mode (C3 is n/a in the benchmark)."}
    prof, defaults = serve.profile(model)
    client = runner.Client(BASE, model, prof, defaults, setup)
    template = runner.PROMPT.read_text()
    original = runner.render(template, q, ds.pages)
    edited = prompt is not None and prompt.strip() != original.strip()
    try:
        if not edited:
            row = runner.run_one(
                q, ds.pages, client, template, checker.load_retry_templates(runner.RETRY), setup, None
            )
        else:
            first = client.ask([{"role": "user", "content": prompt}])
            g = checker.check(first["content"], q, ds.pages)
            row = {"id": q["id"], "setup": setup, "attempts": [first], "retried": False, **checker.as_dict(g)}
    except Exception as e:  # noqa: BLE001 (report any server error to the user)
        return {"error": f"Request failed: {e}"}
    used = prompt if edited else original
    LIVE.mkdir(parents=True, exist_ok=True)
    path = LIVE / f"{datetime.now(UTC):%Y-%m-%d}.jsonl"
    rec = {"time": now(), "set": ds.key, "question_id": q["id"], "model": model, "setup": setup,
           "revision": SERVER.revision(), "edited_prompt": edited,
           "prompt_sha256": hashlib.sha256(used.encode()).hexdigest(), "prompt": used if edited else None,
           "result": row}  # fmt: skip
    with path.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    failed = row.get("failed_check")
    found = (row.get("answer") or {}).get("status") == "found"
    steps, failed_seen = [], False
    for key, label in CHECK_STEPS:
        if failed_seen:
            state = "skipped"  # the checker stops at the first failure
        elif failed == key:
            state, failed_seen = "fail", True
        elif key != "parse" and not found:
            state = "n/a"  # a not_found answer has no page or quote to check
        else:
            state = "pass"
        steps.append({"key": key, "label": label, "state": state})
    stored = ds.answers[q["id"]].get((model, setup))
    a = row.get("answer") or {}
    return {
        "outcome": row["outcome"], "category": row.get("category"), "failed_check": failed,
        "matches_key": row.get("value_matches_gold"), "edited": edited, "retried": row.get("retried", False),
        "answer": {"status": a.get("status"), "value": a.get("value"), "scale": a.get("scale"),
                   "page": a.get("page"), "span": a.get("span")},
        "steps": steps,
        "attempts": [{"content": t.get("content"), "reasoning": (t.get("reasoning") or "")[:20000],
                      "tokens": t.get("completion_tokens"), "seconds": t.get("seconds"),
                      "retry_message": t.get("retry_message")} for t in row.get("attempts", [])],
        "stored": None if not stored else {"outcome": stored["outcome"], "value": (stored.get("answer") or {}).get("value"),
                                           "same_outcome": stored["outcome"] == row["outcome"]},
        "logged_to": str(path.relative_to(ROOT)), "revision": SERVER.revision(),
    }  # fmt: skip


# ---------------------------------------------------------------- review


def review_path(ds: DataSet) -> Path:
    return REVIEW / ds.key / "review.jsonl"


def load_review(ds: DataSet, qid: str) -> dict | None:
    p, last = review_path(ds), None
    if p.exists():
        for line in p.open():
            r = json.loads(line)
            if r["question_id"] == qid:
                last = r
    return last


def reviewed_ids(ds: DataSet) -> set[str]:
    p = review_path(ds)
    return {json.loads(line)["question_id"] for line in p.open()} if p.exists() else set()


def save_review(set_key: str, qid: str, body: dict) -> dict:
    ds = SETS[set_key]
    if qid not in ds.by_id:
        return {"error": "Unknown question."}
    rec = {"time": now(), "question_id": qid, "gold_correct": body.get("gold_correct"),
           "agree_with_checker": body.get("agree_with_checker"), "why_hard": body.get("why_hard") or [],
           "note": body.get("note") or ""}  # fmt: skip
    p = review_path(ds)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"saved": rec, "reviewed": len(reviewed_ids(ds))}
