import tempfile
import unittest
from pathlib import Path
import game
import mythos

class MythosTrialTests(unittest.TestCase):
    def test_catalog(self):
        c = {x["id"]: x for x in game.catalog()}
        self.assertEqual(len(c["mythos"]["scenarios"]), 3)
        self.assertIn("civic-recovery", c)

    def test_play_and_replay(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "session.json"
            v = mythos.start("boothbay", p, 42)
            self.assertEqual(v["turn"], 0)
            self.assertNotIn("attributes", v)
            self.assertNotIn("primary_threat", str(v))
            old = v["revision"]
            v = mythos.act(p, "inspect_docks", old)
            self.assertEqual(v["turn"], 1)
            self.assertEqual(v["time"], "1927-10-13T09:00:00")
            with self.assertRaisesRegex(ValueError, "stale"):
                mythos.act(p, "depart", old)
            v = mythos.act(p, "depart", v["revision"])
            self.assertEqual(v["ending"]["reason"], "depart")
            self.assertEqual(v["choices"], [])
            self.assertEqual(mythos.inspect(p), v)

    def test_limit_and_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "session.json"
            with self.assertRaises(ValueError):
                mythos.start("castine", p, 42)
            v = mythos.start("boothbay", p, 42)
            with self.assertRaises(ValueError):
                mythos.act(p, "report", v["revision"])
            for _ in range(20):
                v = mythos.act(p, "observe", v["revision"])
            self.assertEqual(v["turn"], 20)
            self.assertEqual(v["ending"]["reason"], "limit")
            self.assertEqual(v["choices"], [])

    def test_tamper(self):
        s = mythos.initial("boothbay", 1)
        s["discoveries"].append("invented")
        with self.assertRaisesRegex(ValueError, "replay"):
            mythos.verify(s)
