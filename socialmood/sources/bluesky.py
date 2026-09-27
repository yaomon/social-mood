"""Bluesky: public post search through the public AppView (no account or key needed)."""
from __future__ import annotations

from socialmood import http
from socialmood.names import iso_ts, queries

SEARCH = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def collect(store, names: list[str], topic_of: dict | None = None, log=print) -> int:
    """Newest 100 posts per query for each name."""
    n = 0
    for name in names:
        for q in queries(name):
            try:
                d = http.get_json(SEARCH, {"q": q, "sort": "latest", "limit": 100}, timeout=30, retries=1)
            except Exception as e:
                log(f"  bluesky {q}: {str(e)[:80]}")
                continue
            rows = [(p["uri"], name, "bluesky", iso_ts(p["record"].get("createdAt") or p["indexedAt"]), p["record"].get("text"))
                    for p in d.get("posts", []) if p.get("record")]
            n += store.add("bluesky", rows, topic_of)
    return n
