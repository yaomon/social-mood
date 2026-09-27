"""One module per network. Each has `collect(store, ...) -> int` (how many new rows).

Reddit is optional: delete sources/reddit.py and `reddit` below is None; everything else keeps working.
"""
from socialmood.sources import bluesky, mastodon, youtube

try:
    from socialmood.sources import reddit
except ImportError:          # removed on purpose
    reddit = None

__all__ = ["bluesky", "mastodon", "youtube", "reddit"]
