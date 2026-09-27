"""social-mood: collect public posts about named public figures and score the mood toward them.

    from socialmood import Store
    from socialmood.sources import bluesky, reddit
"""
__version__ = "0.1.0"

from socialmood.store import Store  # noqa: E402

__all__ = ["Store", "__version__"]
