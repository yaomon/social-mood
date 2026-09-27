"""Command line.

    python -m socialmood collect people.yaml              collect from every source that's set up
    python -m socialmood collect people.yaml --no-reddit  skip Reddit
    python -m socialmood score people.yaml --url http://127.0.0.1:11435 --model laya:en --budget 600
    python -m socialmood summary people.yaml

Keys come from the environment: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET (and optionally REDDIT_USERNAME),
YOUTUBE_API_KEY. See examples/people.yaml for the config format.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time

from socialmood import Store, score as scoring, sources
from socialmood.names import aliases


def _config(path: str) -> dict:
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _store(cfg: dict, db: str | None) -> Store:
    return Store(sqlite3.connect(db or cfg.get("db") or "mood.sqlite")).ensure()


def collect(cfg: dict, store: Store, use_reddit: bool = True) -> dict:
    people = [p["name"] for p in cfg.get("people") or []]
    topic_of = {p["name"]: p["topic"] for p in cfg.get("people") or [] if p.get("topic")}
    alias = {n: aliases(n, people) for n in people}
    got = {"bluesky": sources.bluesky.collect(store, people, topic_of),
           "mastodon": sources.mastodon.collect(store, people, topic_of)}
    videos = [tuple(v) for v in cfg.get("youtube_videos") or []]
    if videos:
        got["youtube"] = sources.youtube.collect(store, videos, os.environ.get("YOUTUBE_API_KEY"))
    if use_reddit and sources.reddit:
        got["reddit"] = sources.reddit.collect(store, people, cfg.get("subreddits") or [], topic_of, alias)
    return got


def summary(store: Store, days: float = 7) -> None:
    since = int(time.time() - days * 86400)
    rows = store.con.execute(
        f"SELECT artist, source, COUNT(*), SUM(p_about >= 0.5), SUM(p_about >= 0.5 AND label='positive'), "
        f"SUM(p_about >= 0.5 AND label='negative') FROM {store.table} WHERE created_ts >= ? "
        "GROUP BY artist, source ORDER BY artist, source", (since,)).fetchall()
    print(f"{'who':28} {'source':9} {'posts':>6} {'about':>6} {'net mood':>9}")
    for who, src, n, ab, pos, neg in rows:
        mood = f"{100 * ((pos or 0) - (neg or 0)) / ab:+.0f}" if ab else "-"
        print(f"{who[:28]:28} {src:9} {n:>6} {ab or 0:>6} {mood:>9}")
    print(f"\nnet mood = % positive minus % negative among scored posts about them, last {days:g} days. Every\n"
          "network and community has its own slant: compare one with its own past, not with another.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="socialmood")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("collect", "score", "summary"):
        s = sub.add_parser(name)
        s.add_argument("config")
        s.add_argument("--db")
    sub.choices["collect"].add_argument("--no-reddit", action="store_true")
    sub.choices["score"].add_argument("--url", default="http://127.0.0.1:11435")
    sub.choices["score"].add_argument("--model", default="laya:en")
    sub.choices["score"].add_argument("--budget", type=float, default=600, help="seconds")
    a = p.parse_args(argv)
    cfg = _config(a.config)
    store = _store(cfg, a.db)
    if a.cmd == "collect":
        for src, n in collect(cfg, store, not a.no_reddit).items():
            print(f"{src}: +{n} new")
    elif a.cmd == "score":
        print(f"scored {scoring.score(store, a.url, a.model, a.budget)}, {store.waiting()} waiting")
    else:
        summary(store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
