"""Sdílená HTTP session s opakováním a slušným User-Agentem."""
from __future__ import annotations

import json
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = "RybarskyPruvodce/1.0 (+https://github.com/ferenz-bramborak/sourcing-appka)"

_session = requests.Session()
_session.headers["User-Agent"] = UA
_retry = Retry(total=4, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504))
_session.mount("https://", HTTPAdapter(max_retries=_retry, pool_maxsize=32))
_session.mount("http://", HTTPAdapter(max_retries=_retry, pool_maxsize=32))


def get(url: str, *, delay: float = 0.0, **kw) -> requests.Response:
    if delay:
        time.sleep(delay)
    r = _session.get(url, timeout=kw.pop("timeout", 60), **kw)
    r.raise_for_status()
    return r


def get_json(url: str, attempts: int = 4, **kw):
    """JSON s opakováním i při useknuté/prázdné odpovědi."""
    for i in range(attempts):
        try:
            r = get(url, **kw)
            return r.json()
        except (json.JSONDecodeError, requests.ConnectionError, requests.Timeout):
            if i == attempts - 1:
                raise
            time.sleep(2 * (i + 1))


def get_text(url: str, encoding: str | None = None, **kw) -> str:
    r = get(url, **kw)
    if encoding:
        r.encoding = encoding
    elif r.encoding is None or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text
