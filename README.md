# social-mood

A small, read-only collector for measuring public mood toward named public figures (musicians, election
candidates, parties) over time. It gathers recent public posts that mention them on Bluesky, Mastodon, YouTube
and Reddit, keeps only the ones that name someone on the list, and has a language model running on your own
computer label each one positive, negative or neutral toward that person.

It's the data-collection part of a personal research project that studies whether shifts in public
conversation show up before other public indicators (streaming charts, polls, prediction-market prices). That
project uses simulated money only.

## What it does and doesn't do

| | |
|---|---|
| **Reads** | Public posts and comments only, through each network's official API |
| **Writes** | Nothing, ever. No posting, commenting, voting, messaging, following or moderating |
| **Stores** | Post text, time, where it was said (subreddit / hashtag / video id), the item's id, who it mentions, mood scores |
| **Doesn't store** | Usernames, profiles, account data, anything private |
| **Shares** | Nothing. Data stays in a local SQLite file. Not resold, not shared, not used to train AI models |
| **Rate** | About 100 requests an hour per network; at most 1 request a second to Reddit (limit: 100 a minute) |

## Sources

Each network is one file in [`socialmood/sources/`](socialmood/sources):

- **bluesky.py**: public post search through `api.bsky.app` (no account needed). Newest 100 posts per name.
- **mastodon.py**: public hashtag timeline on mastodon.social (no account needed). Newest 40 per name.
- **youtube.py**: newest 100 top-level comments on listed videos (YouTube Data API v3, your own key).
- **reddit.py**: Reddit's OAuth Data API as a script app (app-only `client_credentials` token, read-only):
  - `GET /search?q="<name>"&sort=new&limit=100`: posts that mention each name
  - `GET /r/<sub>/comments?limit=100`: newest comments in each listed subreddit. A comment is kept only if it
    names someone on the list; the rest are dropped at once and never stored.
  - The User-Agent follows Reddit's format: `python:<client id>:v0.1.0 (personal sentiment analysis tool; by /u/<you>)`

**Reddit is fully optional.** Delete `socialmood/sources/reddit.py` and everything else runs unchanged
(`socialmood.sources.reddit` becomes `None`), or pass `--no-reddit`.

## Matching: is this post really about them?

- Names are matched on whole words, case-insensitively ([`names.py`](socialmood/names.py)).
- A bare surname counts only when it's distinctive: "Paxton" yes, "Golden" or "Bass" no, and never when two
  followed people share it (a bare "Trump" is never credited to Trump Jr.).
- Stage names that are ordinary words ("Future", "Drake") are searched together with a music word.
- The model also answers "is this about that person?" for every post, and the reports drop posts where the
  answer is probably no.

## Mood scoring

[`score.py`](socialmood/score.py) sends each post to a model server on your own machine (an HTTP
`/v1/systemone` endpoint, as served by Ollaya). No post text goes to a third-party AI service. It asks two
questions: is the post about the person, and is it positive, negative or neutral toward them? Musicians and
politicians get differently worded questions.

## Bias

Every network and community has its own slant: Reddit and Bluesky lean left, and each subreddit has its own
culture. So the scores are **never read as a poll**. The intended use compares a community with its own past
(did mood toward a candidate in r/texas shift after a debate, relative to r/texas's usual tone?), and checks
whether communities with different leanings move the same way.

## Use

```bash
pip install -e .
python -m socialmood collect examples/people.yaml               # Bluesky + Mastodon; Reddit/YouTube if keys are set
python -m socialmood score examples/people.yaml --budget 600    # needs a local model server
python -m socialmood summary examples/people.yaml
python -m unittest discover tests
```

Keys come from environment variables: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME` (optional,
for the User-Agent), `YOUTUBE_API_KEY`.

As a library:

```python
import sqlite3
from socialmood import Store
from socialmood.sources import bluesky, reddit

store = Store(sqlite3.connect("mood.sqlite")).ensure()
bluesky.collect(store, ["Taylor Swift"])
if reddit:
    reddit.collect(store, ["Taylor Swift"], subs=["popheads"])
```

## License

MIT
