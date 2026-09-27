"""Deciding whether a post is about someone: search queries, aliases, and matching on word boundaries."""
from __future__ import annotations

import re
from datetime import datetime

# Short forms people actually write.
SHORT_FORMS = {"Democrats": ["Democrats", "Dems", "Democratic Party"],
               "Republicans": ["Republicans", "GOP", "Republican Party"], "Donald Trump": ["Trump"]}
# Surnames that are everyday words or very common: only the full name counts ("Golden" alone is not Jared Golden).
COMMON_WORDS = {"golden", "king", "young", "white", "brown", "green", "black", "rich", "long", "rogers", "hunt", "love",
                "price", "banks", "rice", "lee", "will", "wood", "hill", "moore", "bell", "may", "day", "cash",
                "scott", "jackson", "marshall", "kelly", "graham", "nixon", "moody", "bass", "hilton", "hamilton"}
# Stage names that are ordinary words or shared with famous non-musicians: searched with a music word attached,
# otherwise "Future" returns every post about the future and "Drake" an NFL quarterback.
AMBIGUOUS = {"future", "drake", "ye", "sza", "doja cat"}
MUSIC_WORDS = ("song", "album", "rapper")


def surname(name: str) -> str:
    parts = [w.rstrip(".,") for w in name.split()]
    return parts[-2] if len(parts) > 2 and parts[-1].lower() in {"jr", "sr", "ii", "iii", "iv"} else parts[-1]


def aliases(name: str, others: list[str] = ()) -> list[str]:
    """How a post can name them. The surname alone counts unless it's an everyday word or someone else being
    followed shares it (Trump Jr. never gets a bare "Trump")."""
    if name in SHORT_FORMS:
        return [name] + [a for a in SHORT_FORMS[name] if a != name]
    last = surname(name)
    taken = {a.lower() for o in others if o != name for a in ([surname(o)] + SHORT_FORMS.get(o, []))}
    ok = len(last) >= 5 and last.lower() not in COMMON_WORDS and last.lower() not in taken
    return [name, last] if ok else [name]


def mentions(text: str, names: list[str], alias: dict | None = None) -> str | None:
    """The first followed name the text mentions (whole words, any case), or None."""
    t = text.lower()
    for n in names:
        if any(re.search(r"\b" + re.escape(a.lower()) + r"\b", t) for a in (alias or {}).get(n, [n])):
            return n
    return None


def queries(name: str) -> list[str]:
    """Search queries for a name."""
    if name in SHORT_FORMS:
        return [f'"{SHORT_FORMS[name][0]}"']
    return [f'"{name}" {w}' for w in MUSIC_WORDS] if name.lower() in AMBIGUOUS else [f'"{name}"']


def hashtag(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (SHORT_FORMS.get(name) or [name])[0].lower())


def iso_ts(ts: str) -> int:
    return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
