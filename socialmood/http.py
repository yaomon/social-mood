"""Minimal stdlib HTTP helpers: retry with backoff, a polite per-host gap, and a hard total time limit."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

UA = "social-mood/0.1 (personal sentiment analysis tool; +https://github.com/yaomon/social-mood)"
HOST_GAP_S = 0.5                       # at most ~2 requests a second to any one host
HOST_GAP = {"oauth.reddit.com": 1.0}   # Reddit allows 100 a minute; stay well under it
_last_hit: dict[str, float] = {}


def _throttle(url: str) -> None:
    host = urllib.parse.urlparse(url).netloc
    wait = _last_hit.get(host, 0) + HOST_GAP.get(host, HOST_GAP_S) - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.time()


def _read_all(r, deadline: float) -> bytes:
    """Read a response but give up at `deadline`: the socket timeout only fires after that much silence, so a
    server trickling bytes could otherwise hold the caller forever."""
    parts = []
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError("response took longer than the total time limit")
        chunk = r.read(65536)
        if not chunk:
            return b"".join(parts)
        parts.append(chunk)


def request(url: str, params: dict | None = None, *, method: str = "GET", body: Any = None, form: dict | None = None,
            headers: dict | None = None, timeout: float = 30, retries: int = 2) -> bytes:
    if params:
        url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})}"
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    hdrs.update(headers or {})
    data = None
    if body is not None:
        data, hdrs["Content-Type"] = json.dumps(body).encode(), "application/json"
    elif form is not None:
        data, hdrs["Content-Type"] = urllib.parse.urlencode(form).encode(), "application/x-www-form-urlencoded"
    delay = 1.0
    for attempt in range(retries + 1):
        _throttle(url)
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return _read_all(r, time.monotonic() + 3 * timeout)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(float(e.headers.get("Retry-After") or delay) if e.code == 429 else delay)
                delay *= 2
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def get_json(url: str, params: dict | None = None, **kw) -> Any:
    return json.loads(request(url, params, **kw))


def post_json(url: str, body: Any, **kw) -> Any:
    return json.loads(request(url, method="POST", body=body, **kw))


def post_form(url: str, form: dict, **kw) -> Any:
    return json.loads(request(url, method="POST", form=form, **kw))
