"""YouTube: newest top-level comments on given videos (YouTube Data API v3; needs your own API key).

Each call costs 1 quota unit (10,000 a day free). A video is re-read at most every `every_s` seconds.
"""
from __future__ import annotations

import time

from socialmood import http
from socialmood.names import iso_ts

THREADS = "https://www.googleapis.com/youtube/v3/commentThreads"


def collect(store, videos: list[tuple[str, str]], key: str | None, every_s: int = 3 * 3600, log=print) -> int:
    """videos: (video_id, who it's about). Returns how many comments were new."""
    if not key:
        return 0
    now, last, n = int(time.time()), store.state("yt_last", {}), 0
    for vid, name in videos:
        if now - last.get(vid, 0) < every_s:
            continue
        try:
            d = http.get_json(THREADS, {"part": "snippet", "videoId": vid, "maxResults": 100, "order": "time",
                                        "textFormat": "plainText", "key": key}, timeout=30, retries=1)
        except Exception as e:          # comments disabled on this video, etc.
            last[vid] = now
            if "403" not in str(e):
                log(f"  youtube comments {vid}: {e}")
            continue
        rows = []
        for it in d.get("items", []):
            sn = it["snippet"]["topLevelComment"]["snippet"]
            rows.append((it["id"], name, vid, iso_ts(sn["publishedAt"]), sn.get("textDisplay")))
        n += store.add("youtube", rows)
        last[vid] = now
    store.set_state("yt_last", last)
    return n
