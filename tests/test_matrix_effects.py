"""Eight-turn synthetic matrix qualification; not a historical scenario."""
import unittest
from age_runtime.core import runner
from age_runtime.core.observations import observe
from age_runtime.core.decision_support import decision_brief


def scenario():
    return {
        "version": 1, "id": "synthetic-matrix", "turn_minutes": 10, "end_minute": 80,
        "initial": {"free": 6, "depleted": 0, "grain": 8, "support": 5},
        "events": [], "constraints": [],
        "actors": {
            "deity": {"label": "Synthetic deity", "visible_keys": ["free", "depleted", "support"],
                      "objectives": {"influence": {"key": "support", "threshold": 7,
                                      "comparison": "at_least", "description": "Increase support"}}},
            "council": {"label": "Independent council", "visible_keys": ["grain", "support"],
                        "objectives": {"autonomy": {"key": "support", "threshold": 5,
                                        "comparison": "at_most", "description": "Limit influence"}}}},
        "model_factions": ["council"],
        "action_catalog": {"intervene": {"description": "Intervene", "actors": ["deity"]},
                           "resist": {"description": "Resist", "actors": ["council"]}},
        "reserve_accounts": {"pr": {"owner": "deity", "capacity": 6, "available": "free",
                                      "depleted": "depleted", "commitments": {}, "recovery": 1}},
        "reserve_actions": {"intervene": {"account": "pr", "operation": "spend",
                                          "amount": 3, "commitment": None}},
        "stock_accounts": {"food": {"owner": "council", "key": "grain", "unit": "grain"}},
        "stock_actions": {"resist": {"source": "food", "destination": None,
                                      "amount": 2, "purpose": "Institutional response"}},
        "matrix_properties": {"support": {"minimum": 0, "maximum": 10}},
        "matrix_effects": {"intervene": {"support": 3}, "resist": {"support": -3}}}


def model_choice(s, state, action):
    packet = runner.faction_packet(s, state, "council")
    return runner.accept_faction_choice(s, state, "council", packet,
                                         {"packet_id": packet["packet_id"], "action": action})


class MatrixEffectsTests(unittest.TestCase):
    def test_opposition_and_replay(self):
        s = scenario()
        state = runner.submit_request(s, runner.initialize(s), "deity", {"action": "intervene"})
        state = model_choice(s, state, "resist")
        state = runner.advance(s, state)
        runner.verify_checkpoint(s, state)
        self.assertEqual(state["values"], {"free": 3, "depleted": 3, "grain": 6, "support": 5})
        self.assertEqual([r["matrix_contribution"] for r in state["requests"]],
                         [{"support": 3}, {"support": -3}])

    def test_unfunded_effect_is_not_applied(self):
        s = scenario()
        state = runner.initialize(s)
        for _ in range(3):
            state = runner.submit_request(s, state, "deity", {"action": "intervene"})
        state = runner.advance(s, model_choice(s, state, None))
        runner.verify_checkpoint(s, state)
        self.assertEqual(state["values"], s["initial"])
        self.assertTrue(all("matrix_contribution" not in r for r in state["requests"]))

    def test_bounds_apply_after_aggregation(self):
        s = scenario()
        s["initial"]["support"] = 9
        for council_first in (False, True):
            state = runner.initialize(s)
            if council_first:
                state = model_choice(s, state, "resist")
            state = runner.submit_request(s, state, "deity", {"action": "intervene"})
            if not council_first:
                state = model_choice(s, state, "resist")
            state = runner.advance(s, state)
            runner.verify_checkpoint(s, state)
            self.assertEqual(state["values"]["support"], 9)

    def test_reject_overlapping_writer(self):
        for key in ("free", "grain"):
            s = scenario()
            s["matrix_properties"][key] = {"minimum": 0, "maximum": 10}
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner.initialize(s)

    def test_private_options(self):
        s = scenario()
        state = runner.submit_request(s, runner.initialize(s), "deity", {"action": "intervene"})
        brief = decision_brief(observe(s, state, "council"))
        self.assertEqual(brief["matrix"]["own_options"], {"resist": {"support": -3}})
        self.assertNotIn("free", observe(s, state, "council")["values"])
        self.assertFalse(observe(s, state, "council")["own_requests"])

    def test_eight_turns_diverge_by_mortal_choice(self):
        s = scenario()
        results = []
        for resist in (False, True):
            state = runner.initialize(s)
            for _ in range(8):
                state = runner.submit_request(s, state, "deity", {"action": "intervene"})
                state = runner.advance(s, model_choice(s, state, "resist" if resist else None))
                runner.verify_checkpoint(s, state)
            self.assertEqual(state["turn"], 8)
            self.assertEqual(state["minute"], 80)
            results.append(state["values"]["support"])
        self.assertGreater(results[0], results[1])
