"""Mood scoring: asks a local language model, per post, whether it's about the person and what attitude it takes.

The model is reached over HTTP at a `/v1/systemone` endpoint that takes {"model", "state", "questions"} and returns
{"answers": {name: {"choice", "probabilities", "noul"}}} (the Ollaya server's API). Any server that speaks that
shape works; nothing leaves your machine if the server is local.

Music (rows without a topic) and topic rows (e.g. politics) take turns, so a flood of one can't starve the other.
"""
from __future__ import annotations

import itertools
import time

from socialmood import http

MUSIC_Q = {"about": {"type": "noul",
                     "instructions": "Is this comment about the musician named in 'about' or their music?",
                     "criteria": {"true": "It is about that musician, their songs, videos, albums or shows.",
                                  "false": "It is about someone or something else that shares the name "
                                           "(an athlete, a word, a place), or has nothing to do with them."}},
           "sentiment": {"type": "choice",
                         "instructions": "What is the commenter's attitude toward the artist or their music?",
                         "criteria": {"positive": "Praise, love, excitement, hype, nostalgia, anticipation.",
                                      "negative": "Criticism, boredom, dislike, disappointment, backlash.",
                                      "neutral": "Jokes, facts, questions, or no clear attitude."}}}
POLITICS_Q = {"about": {"type": "noul",
                        "instructions": "Is this comment about the politician or party named in 'about'?",
                        "criteria": {"true": "It talks about that politician or party, their record, campaign or chances.",
                                     "false": "It is about someone else with that name, or doesn't concern them."}},
              "sentiment": {"type": "choice",
                            "instructions": "What is the commenter's attitude toward the politician or party in 'about'?",
                            "criteria": {"positive": "Support, praise, confidence they'll win, defending them.",
                                         "negative": "Opposition, criticism, mockery, expecting or wanting them to lose.",
                                         "neutral": "News, facts, questions, or no clear attitude toward them."}}}


def ask(url: str, model: str, source: str, who: str, text: str, topic: str | None) -> tuple:
    """(label, p_pos, p_neg, p_neu, p_about) for one post."""
    # A YouTube comment sits under the artist's own video, so it's about them by construction (a bare "way too
    # short" is about the song); the model is told where it was posted so the mood has context.
    on_video = source == "youtube" and topic is None
    state = {"about": who, "comment": text[:1000]}
    if on_video:
        state["posted_under"] = f"{who}'s own music video on YouTube"
    questions = POLITICS_Q if topic else {"sentiment": MUSIC_Q["sentiment"]} if on_video else MUSIC_Q
    r = http.post_json(url.rstrip("/") + "/v1/systemone", {"model": model, "state": state, "questions": questions},
                       timeout=60, retries=1)
    a = r["answers"]["sentiment"]
    p = a.get("probabilities") or {}
    p_about = 1.0 if on_video else (r["answers"].get("about") or {}).get("noul")      # noul = P(true)
    return a.get("choice"), p.get("positive"), p.get("negative"), p.get("neutral"), p_about


def score(store, url: str, model: str, budget_s: float = 1500) -> int:
    """Score unscored rows, newest first, until the time budget runs out. Returns how many were scored."""
    if budget_s <= 0:
        return 0
    t0, n = time.time(), 0
    while time.time() - t0 < budget_s:
        batch = [r for pair in itertools.zip_longest(store.unscored(False, 25), store.unscored(True, 25))
                 for r in pair if r]
        if not batch:
            break
        for source, item, who, text, topic in batch:
            if time.time() - t0 >= budget_s:
                break
            try:
                vals = ask(url, model, source, who, text, topic)
            except Exception as e:
                if "Connection" in str(e) or "refused" in str(e):
                    raise RuntimeError(f"the scoring model isn't answering at {url}: {e}") from None
                vals = ("error", None, None, None, None)
            store.set_score(source, item, *vals)
            n += 1
    return n
