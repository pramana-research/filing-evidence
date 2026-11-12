"""Download SEC EDGAR data: ticker->CIK map, XBRL company facts, filing index.

SEC rules: send a descriptive User-Agent with contact info, and stay under 10 requests/second.
https://www.sec.gov/os/accessing-edgar-data
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

_MIN_INTERVAL = 0.15  # ~6-7 req/s, safely under the SEC limit


class EdgarClient:
    def __init__(self, user_agent: str | None = None, cache_dir: Path | None = None):
        ua = user_agent or os.environ.get("SEC_USER_AGENT")
        if not ua or "@" not in ua:
            raise ValueError("Set SEC_USER_AGENT to 'Company Name email@domain' (SEC requirement)")
        self._http = httpx.Client(headers={"User-Agent": ua}, timeout=60, follow_redirects=True)
        self._last = 0.0
        self.cache_dir = cache_dir

    def _get_json(self, url: str, cache_name: str | None = None) -> dict:
        if self.cache_dir and cache_name:
            cached = self.cache_dir / cache_name
            if cached.exists():
                return json.loads(cached.read_text())
        wait = _MIN_INTERVAL - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(4):
            resp = self._http.get(url)
            self._last = time.monotonic()
            if resp.status_code in (429, 503):
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            if self.cache_dir and cache_name:
                (self.cache_dir / cache_name).parent.mkdir(parents=True, exist_ok=True)
                (self.cache_dir / cache_name).write_text(json.dumps(data))
            return data
        raise RuntimeError(f"SEC kept throttling: {url}")

    def ticker_to_cik(self) -> dict[str, int]:
        raw = self._get_json(TICKERS_URL, "company_tickers.json")
        return {row["ticker"].upper(): int(row["cik_str"]) for row in raw.values()}

    def company_facts(self, cik: int) -> dict:
        return self._get_json(FACTS_URL.format(cik=cik), f"facts/CIK{cik:010d}.json")

    def submissions(self, cik: int) -> dict:
        return self._get_json(SUBMISSIONS_URL.format(cik=cik), f"submissions/CIK{cik:010d}.json")
