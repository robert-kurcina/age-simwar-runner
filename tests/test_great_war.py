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


    def test_independent_deity_packets_and_full_plays(self):
        s = self.s
        observed_taps = 0
        for seed in range(8):
            session = gw.start(s, seed)
            while not gw.complete(s, session["state"]):
                actor = s["deities"][session["state"]["active"]]
                other = next(a for a in s["deities"] if a != actor)
                packet = gw.decision_packet(s, session, actor)
                view = packet["observation"]
                self.assertEqual(gw.observe(s, session, other)["choices"], [])
                with self.assertRaises(ValueError):
                    gw.decision_packet(s, session, other)
                before = deepcopy(session)
                for command in view["choices"]:
                    gw.play(s, session["state"], actor, command)
                self.assertEqual(session, before)
                # Prefer a legal Tap, otherwise advance history when possible.
                choices = view["choices"]
                index = next((i for i, c in enumerate(choices) if c["tap"] is not None),
                             next((i for i, c in enumerate(choices) if view["hand"][c["card"]]["time"]), 0))
                observed_taps += int(choices[index]["tap"] is not None)
                response = {"packet_id": packet["packet_id"], "choice": index}
                for bad in ({**response, "choice": True}, {**response, "choice": len(choices)},
                            {**response, "packet_id": "stale"}, {**response, "effects": {}}):
                    with self.assertRaises(ValueError):
                        gw.resolve_choice(s, session, actor, bad)
                session = gw.resolve_choice(s, session, actor, response)
                with self.assertRaises(ValueError):
                    gw.resolve_choice(s, session, actor, response)
                self.assertEqual(gw.verify(s, session), session)
            self.assertEqual(session["state"]["year"], s["endpoint"])
        self.assertGreater(observed_taps, 0)

    def test_required_card_with_no_legal_icon_is_not_offered(self):
        s = self.s
        session = gw.start(s, 4)
        actor = s["deities"][0]
        cid = next(iter(gw.observe(s, session, actor)["hand"]))
        s["cards"][cid].update(event="quiet", tap="required")
        session = gw.start(s, 4)
        self.assertFalse(any(c["card"] == cid for c in gw.observe(s, session, actor)["choices"]))


    def test_choice_assessment_is_exact_private_and_advisory(self):
        s = self.s
        saw_tap = False
        for seed in range(8):
            session = gw.start(s, seed)
            while not gw.complete(s, session["state"]):
                actor = s["deities"][session["state"]["active"]]
                other = next(a for a in s["deities"] if a != actor)
                view = gw.decision_packet(s, session, actor)["observation"]
                self.assertEqual(view["motivation"], s["motivations"][actor])
                self.assertNotIn(s["motivations"][other], json.dumps(view))
                before = deepcopy(session)
                for cmd, assessment in zip(view["choices"], view["choice_assessments"]):
                    after = gw.play(s, session["state"], actor, cmd)
                    self.assertEqual(assessment["year_after"], after["year"])
                    self.assertEqual(assessment["ends_rehearsal"], gw.complete(s, after))
                    for row in assessment["own_prominence_changes"]:
                        self.assertEqual(after["piles"][row["pile"]]["deity"], actor)
                        self.assertEqual(row["after"], after["piles"][row["pile"]]["pl"])
                self.assertEqual(session, before)
                index = next((i for i, c in enumerate(view["choices"]) if c["tap"] is not None), 0)
                saw_tap |= view["choices"][index]["tap"] is not None
                session = gw.commit(s, session, actor, view["revision"], view["choices"][index])
        self.assertTrue(saw_tap)
        altered = deepcopy(s)
        altered["motivations"] = {a: "Contrasting preference." for a in s["deities"]}
        a, b = gw.start(s, 42), gw.start(altered, 42)
        self.assertEqual(a["state"], b["state"])
        actor = s["deities"][0]
        self.assertEqual(gw.observe(s, a, actor)["choices"], gw.observe(altered, b, actor)["choices"])
        bad = deepcopy(s)
        bad["motivations"].pop(actor)
        with self.assertRaises(ValueError):
            gw.validate(bad)
