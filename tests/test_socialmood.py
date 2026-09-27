import sqlite3
import unittest
from unittest import mock

from socialmood import Store, score
from socialmood import sources
from socialmood.names import aliases, mentions, queries


def store():
    return Store(sqlite3.connect(":memory:")).ensure()


class NamesTest(unittest.TestCase):
    def test_aliases_skip_common_and_shared_surnames(self):
        people = ["Donald Trump", "Donald J. Trump Jr.", "Ken Paxton", "Jared Golden", "Angus King III", "Democrats"]
        self.assertEqual(aliases("Donald Trump", people), ["Donald Trump", "Trump"])
        self.assertEqual(aliases("Donald J. Trump Jr.", people), ["Donald J. Trump Jr."])
        self.assertEqual(aliases("Ken Paxton", people), ["Ken Paxton", "Paxton"])
        self.assertEqual(aliases("Jared Golden", people), ["Jared Golden"])
        self.assertEqual(aliases("Angus King III", people), ["Angus King III"])
        self.assertIn("GOP", aliases("Republicans", people))

    def test_mentions_whole_words(self):
        a = {"Ken Paxton": ["Ken Paxton", "Paxton"]}
        self.assertEqual(mentions("Paxton is done", ["Ken Paxton"], a), "Ken Paxton")
        self.assertIsNone(mentions("Paxtonville news", ["Ken Paxton"], a))

    def test_queries(self):
        self.assertEqual(queries("Future"), ['"Future" song', '"Future" album', '"Future" rapper'])
        self.assertEqual(queries("Donald Trump"), ['"Trump"'])


class StoreTest(unittest.TestCase):
    def test_add_dedupes_tags_topic_and_skips_empty(self):
        s = store()
        rows = [("1", "Ken Paxton", "r/texas", 1, "hi"), ("2", "Taylor Swift", "bluesky", 1, "yo"), ("3", "X", "c", 1, " ")]
        self.assertEqual(s.add("reddit", rows, {"Ken Paxton": "senate-tx"}), 2)
        self.assertEqual(s.add("reddit", rows), 0)
        self.assertEqual(dict(s.con.execute("SELECT item_id, topic FROM comments")), {"1": "senate-tx", "2": None})

    def test_migrates_old_table(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE old (source TEXT, item_id TEXT, artist TEXT, context TEXT, created_ts INTEGER, "
                    "seen_ts INTEGER, text TEXT, label TEXT, p_pos REAL, p_neg REAL, p_neu REAL, scored_ts INTEGER, "
                    "PRIMARY KEY (source, item_id))")
        s = Store(con, table="old").ensure()
        self.assertEqual(s.add("x", [("1", "A", "c", 1, "t")], {"A": "t1"}), 1)

    def test_rejects_odd_table_names(self):
        with self.assertRaises(ValueError):
            Store(sqlite3.connect(":memory:"), table="x; DROP TABLE y")


class ScoreTest(unittest.TestCase):
    def test_takes_turns_and_picks_questions(self):
        s = store()
        s.add("bluesky", [(str(i), "Taylor Swift", "bluesky", 100 + i, "love it") for i in range(3)])
        s.add("reddit", [("p", "Ken Paxton", "r/texas", 50, "no way")], {"Ken Paxton": "senate-tx"})
        seen = []

        def fake(url, body, **kw):
            seen.append(("politics" if "politician" in body["questions"]["about"]["instructions"] else "music"))
            return {"answers": {"sentiment": {"choice": "positive", "probabilities": {"positive": .9}},
                                "about": {"noul": .8}}}
        with mock.patch.object(score.http, "post_json", fake):
            self.assertEqual(score.score(s, "http://x", "m", budget_s=60), 4)
        self.assertEqual(seen[:2], ["music", "politics"])       # the single politics row isn't left for last
        self.assertEqual(s.waiting(), 0)


class SeparableTest(unittest.TestCase):
    def test_other_sources_do_not_import_reddit(self):
        import inspect
        for mod in (sources.bluesky, sources.mastodon, sources.youtube, score):
            self.assertNotIn("reddit", inspect.getsource(mod).lower().replace("reddit.com", ""), mod.__name__)

    def test_reddit_without_credentials_does_nothing(self):
        if not sources.reddit:
            self.skipTest("reddit.py removed")
        with mock.patch.dict("os.environ", {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}):
            self.assertEqual(sources.reddit.collect(store(), ["A"], ["popheads"]), 0)


if __name__ == "__main__":
    unittest.main()
