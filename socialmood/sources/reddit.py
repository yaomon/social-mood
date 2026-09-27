"""Reddit: read-only, through Reddit's OAuth Data API with a script app's client credentials.

Self-contained on purpose: delete this file and the rest of social-mood works without Reddit
(`socialmood.sources.reddit` is then None).

What it does, each run:
  1. Gets an app-only access token (client_credentials grant: no user account, read-only).
  2. For each name: GET /search?q="<name>"&sort=new&limit=100  (posts that mention them)
  3. For each subreddit: GET /r/<sub>/comments?limit=100  (newest comments; kept only if they name someone
     followed, the rest are discarded immediately)
It never posts, comments, votes, messages or reads anything private. It stores no usernames. At most one
request a second (Reddit allows 100 a minute).
"""
from __future__ import annotations

import base64
import os
import time

from socialmood import __version__, http
from socialmood.names import mentions, queries

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API = "https://oauth.reddit.com"
_token: tuple[float, str, str] | None = None      # (expires, client id, token)


def credentials() -> tuple[str | None, str | None]:
    return os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")


def user_agent(client_id: str | None) -> dict:
    """Reddit asks for '<platform>:<app id>:<version> (by /u/<username>)'. Set REDDIT_USERNAME to add the last part."""
    who = os.environ.get("REDDIT_USERNAME")
    return {"User-Agent": f"python:{client_id or 'social-mood'}:v{__version__} (personal sentiment analysis tool"
                          + (f"; by /u/{who})" if who else ")")}


def token(client_id: str | None = None, client_secret: str | None = None) -> str | None:
    """An app-only token, reused until 5 minutes before it expires. None when there are no credentials."""
    global _token
    if not client_id or not client_secret:
        client_id, client_secret = credentials()
    if not client_id or not client_secret:
        return None
    if _token and _token[1] == client_id and time.time() < _token[0]:
        return _token[2]
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    d = http.post_form(TOKEN_URL, {"grant_type": "client_credentials"},
                       headers={**user_agent(client_id), "Authorization": f"Basic {basic}"})
    _token = (time.time() + int(d.get("expires_in", 3600)) - 300, client_id, d["access_token"])
    return _token[2]


def collect(store, names: list[str], subs: list[str], topic_of: dict | None = None, alias: dict | None = None,
            client_id: str | None = None, client_secret: str | None = None, log=print) -> int:
    """Posts that mention each name, plus newest comments in `subs` that mention one. Returns how many were new."""
    tok = token(client_id, client_secret)
    if not tok:
        return 0
    hdr = {**user_agent(client_id or credentials()[0]), "Authorization": f"bearer {tok}"}
    n = 0
    for name in names:
        try:
            d = http.get_json(f"{API}/search", {"q": queries(name)[0], "sort": "new", "limit": 100, "type": "link",
                                                "raw_json": 1}, headers=hdr, timeout=30)
        except Exception as e:
            log(f"  reddit search {name}: {str(e)[:80]}")
            continue
        rows = [(c["data"]["name"], name, "r/" + c["data"].get("subreddit", ""), int(c["data"]["created_utc"]),
                 (c["data"].get("title") or "") + "\n" + (c["data"].get("selftext") or ""))
                for c in d.get("data", {}).get("children", [])]
        n += store.add("reddit", rows, topic_of)
    for sub in subs:
        try:
            d = http.get_json(f"{API}/r/{sub}/comments", {"limit": 100, "raw_json": 1}, headers=hdr, timeout=30)
        except Exception as e:
            log(f"  reddit r/{sub}: {str(e)[:80]}")
            continue
        rows = []
        for c in d.get("data", {}).get("children", []):
            body = c["data"].get("body") or ""
            who = mentions(body, names, alias)
            if who:
                rows.append((c["data"]["name"], who, f"r/{sub}", int(c["data"]["created_utc"]), body))
        n += store.add("reddit", rows, topic_of)
    return n


def check(client_id: str | None = None, client_secret: str | None = None) -> str:
    """One harmless read to prove the credentials work. Returns the newest r/popheads post title."""
    tok = token(client_id, client_secret)
    if not tok:
        raise RuntimeError("no Reddit client ID and secret")
    d = http.get_json(f"{API}/r/popheads/new", {"limit": 1},
                      headers={**user_agent(client_id or credentials()[0]), "Authorization": f"bearer {tok}"}, timeout=30)
    return d["data"]["children"][0]["data"]["title"]
