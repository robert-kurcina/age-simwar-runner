import json
import unittest
from copy import deepcopy
from age_runtime.core import great_war as gw
from age_runtime.core.runner import digest


class GreatWarTests(unittest.TestCase):
    def setUp(self):
        self.s = json.loads(gw.SPEC.read_text())

    def test_native_lifecycle(self):
        s = self.s
        state = gw.initialize(s, 42)
        state["founts"]["fixture"] = {"region": "north", "status": "hidden", "controller": "amber"}
        with self.assertRaises(ValueError):
            gw.tap(s, deepcopy(state), "azure", {"fount": "fixture", "pile": "azure_n", "disposition": "N1"}, "north")
        gw.tap(s, state, "amber", {"fount": "fixture", "pile": "amber_n", "disposition": "N1"}, "north")
        self.assertEqual(state["piles"]["amber_n"]["pl"], 4)
        self.assertEqual(state["founts"]["fixture"]["status"], "wondrous")
        with self.assertRaises(ValueError):
            gw.tap(s, deepcopy(state), "amber", {"fount": "fixture", "pile": "amber_n", "disposition": None}, "north")
        gw.tap(s, state, "azure", {"fount": "fixture", "pile": "azure_n", "disposition": None}, "north")
        self.assertEqual(state["piles"]["azure_n"]["pl"], 12)
        self.assertEqual(state["founts"]["fixture"]["status"], "emitter")
        # A zero-Time Event leaves the drained state intact.
        state["hands"]["amber"] = ["event-04"]
        state = gw.play(s, state, "amber", {"card": "event-04", "tap": None})
        self.assertEqual(state["year"], 0)
        self.assertEqual(state["founts"]["fixture"]["status"], "emitter")
        state["hands"]["azure"] = ["event-06"]
        state = gw.play(s, state, "azure", {"card": "event-06", "tap": None})
        self.assertEqual(state["year"], 1)
        self.assertEqual(state["founts"]["fixture"]["status"], "wondrous")
        self.assertEqual(state["tapped"], [])
        gw.tap(s, state, "amber", {"fount": "fixture", "pile": "amber_n", "disposition": None}, "north")
        gw.tap(s, state, "azure", {"fount": "fixture", "pile": "azure_n", "disposition": None}, "north")
        self.assertNotIn("fixture", state["founts"])

    def test_replay_and_hidden_state(self):
        s = self.s
        for seed in range(6):
            session = gw.start(s, seed)
            while not gw.complete(s, session["state"]):
                actor = s["deities"][session["state"]["active"]]
                view = gw.observe(s, session, actor)
                other = next(a for a in s["deities"] if a != actor)
                self.assertNotIn("deck", view)
                self.assertNotIn("hands", view)
                self.assertTrue(all("pl" not in p for p in view["piles"].values() if p["deity"] == other))
                card = next(iter(view["hand"]))
                before = deepcopy(session)
                with self.assertRaises(ValueError):
                    gw.commit(s, session, other, view["revision"], {"card": card, "tap": None})
                with self.assertRaises(ValueError):
                    gw.commit(s, session, actor, "stale", {"card": card, "tap": None})
                self.assertEqual(session, before)
                session = gw.commit(s, session, actor, view["revision"], {"card": card, "tap": None})
                self.assertEqual(gw.verify(s, session), session)
            self.assertEqual(session["state"]["year"], 5)
            bad = deepcopy(session)
            bad["state"]["year"] = 0
            with self.assertRaises(ValueError):
                gw.verify(s, bad)

    def test_required_icon_atomic(self):
        s = self.s
        session = gw.start(s, 4)
        actor = s["deities"][0]
        card = next(iter(gw.observe(s, session, actor)["hand"]))
        s["cards"][card]["tap"] = "required"
        session = gw.start(s, 4)
        before = deepcopy(session)
        with self.assertRaises(ValueError):
            gw.commit(s, session, actor, digest(session), {"card": card, "tap": None})
        self.assertEqual(before, session)
