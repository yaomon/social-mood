"""Mastodon: public hashtag timelines on one instance (no account or key needed)."""
from __future__ import annotations

import re

from socialmood import http
from socialmood.names import hashtag, iso_ts

INSTANCE = "https://mastodon.social"


def collect(store, names: list[str], topic_of: dict | None = None, instance: str = INSTANCE, log=print) -> int:
    """Newest 40 posts under each name's hashtag (#kenpaxton, #taylorswift)."""
    n = 0
    for name in names:
        tag = hashtag(name)
        try:
            d = http.get_json(f"{instance}/api/v1/timelines/tag/{tag}", {"limit": 40}, timeout=30, retries=1)
        except Exception as e:
            log(f"  mastodon #{tag}: {str(e)[:80]}")
            continue
        rows = [(s["uri"], name, f"#{tag}", iso_ts(s["created_at"]), re.sub(r"<[^>]+>", " ", s.get("content") or ""))
                for s in d if isinstance(s, dict)]
        n += store.add("mastodon", rows, topic_of)
    return n
