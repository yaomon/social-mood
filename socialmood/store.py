"""SQLite storage: one row per post or comment, plus a small key/value table for collector state.

A row holds the source, the source's own id for the item, who it's about, where it was said (subreddit, hashtag,
video id), when it was posted and first seen, the text, and later the mood scores. No usernames or account data.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Store:
    def __init__(self, con: sqlite3.Connection, table: str = "comments", state_table: str = "collector_state"):
        if not (_NAME.match(table) and _NAME.match(state_table)):
            raise ValueError("table names must be plain identifiers")
        self.con, self.table, self.state_table = con, table, state_table

    def ensure(self) -> "Store":
        """Create the tables, and add columns older versions didn't have."""
        t = self.table
        self.con.executescript(f"""
            CREATE TABLE IF NOT EXISTS {t} (
                source TEXT, item_id TEXT, artist TEXT, context TEXT, created_ts INTEGER, seen_ts INTEGER, text TEXT,
                label TEXT, p_pos REAL, p_neg REAL, p_neu REAL, scored_ts INTEGER, p_about REAL, topic TEXT,
                PRIMARY KEY (source, item_id));
            CREATE TABLE IF NOT EXISTS {self.state_table} (key TEXT PRIMARY KEY, value TEXT);""")
        cols = {r[1] for r in self.con.execute(f"PRAGMA table_info({t})")}
        for col, typ in (("p_about", "REAL"), ("topic", "TEXT")):
            if col not in cols:
                self.con.execute(f"ALTER TABLE {t} ADD COLUMN {col} {typ}")
        self.con.executescript(f"""
            CREATE INDEX IF NOT EXISTS {t}_unscored ON {t}(scored_ts, created_ts);
            CREATE INDEX IF NOT EXISTS {t}_artist ON {t}(artist, created_ts);
            CREATE INDEX IF NOT EXISTS {t}_topic ON {t}(topic, created_ts);""")
        return self

    # `artist` is the column's historical name: it holds whoever the row is about (an artist, a politician, a party).
    def add(self, source: str, rows: list[tuple], topic_of: dict | None = None) -> int:
        """rows: (item_id, who, context, created_ts, text). topic_of maps a person to a topic id (None = no topic).
        Returns how many rows were new."""
        now, topic_of = int(time.time()), topic_of or {}
        with self.con:
            before = self.con.total_changes
            self.con.executemany(
                f"INSERT OR IGNORE INTO {self.table} (source, item_id, artist, context, created_ts, seen_ts, text, topic) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [(source, i, a, c, t, now, (x or "")[:2000], topic_of.get(a)) for i, a, c, t, x in rows if x and x.strip()])
            return self.con.total_changes - before

    def state(self, key: str, default=None):
        r = self.con.execute(f"SELECT value FROM {self.state_table} WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def set_state(self, key: str, value) -> None:
        with self.con:
            self.con.execute(f"INSERT OR REPLACE INTO {self.state_table} VALUES (?,?)", (key, json.dumps(value)))

    def unscored(self, with_topic: bool, limit: int) -> list[tuple]:
        return self.con.execute(
            f"SELECT source, item_id, artist, text, topic FROM {self.table} WHERE scored_ts IS NULL "
            f"AND topic IS {'NOT ' if with_topic else ''}NULL ORDER BY created_ts DESC LIMIT ?", (limit,)).fetchall()

    def set_score(self, source: str, item_id: str, label, p_pos, p_neg, p_neu, p_about) -> None:
        with self.con:
            self.con.execute(f"UPDATE {self.table} SET label=?, p_pos=?, p_neg=?, p_neu=?, p_about=?, scored_ts=? "
                             "WHERE source=? AND item_id=?",
                             (label, p_pos, p_neg, p_neu, p_about, int(time.time()), source, item_id))

    def waiting(self) -> int:
        return self.con.execute(f"SELECT COUNT(*) FROM {self.table} WHERE scored_ts IS NULL").fetchone()[0]
