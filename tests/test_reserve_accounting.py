"""Synthetic reserve-accounting integration; no historical calibration."""
import copy
import unittest
from age_runtime.core import runner


def scenario():
    actions = {"hold": ("reserve", 4, "project"), "spend": ("spend", 4, None),
               "release": ("release", None, "project"), "consume": ("consume", None, "project")}
    return {"version": 1, "id": "reserve-test", "turn_minutes": 10, "end_minute": 80,
            "initial": {"free": 6, "used": 0, "project": 0},
            "events": [], "constraints": [],
            "actors": {"deity": {"label": "Test deity", "visible_keys": ["free", "used", "project"]}},
            "action_catalog": {name: {"description": name, "actors": ["deity"]} for name in actions},
            "reserve_accounts": {"pr": {"owner": "deity", "capacity": 6, "available": "free",
                                         "depleted": "used", "commitments": {"project": "project"},
                                         "recovery": 2}},
            "reserve_actions": {name: {"account": "pr", "operation": op, "amount": amount,
                                        "commitment": slot} for name, (op, amount, slot) in actions.items()}}


class ReserveAccountingTests(unittest.TestCase):
    def run_turn(self, s, state, *actions):
        for action in actions:
            state = runner.submit_request(s, state, "deity", {"action": action})
        state = runner.advance(s, state)
        runner.verify_checkpoint(s, state)
        return state

    def test_reserve_release_consume_and_recovery(self):
        s = scenario()
        state = self.run_turn(s, runner.initialize(s), "hold")
        self.assertEqual(state["values"], {"free": 2, "used": 0, "project": 4})
        state = self.run_turn(s, state, "release")
        self.assertEqual(state["values"], s["initial"])
        state = self.run_turn(s, state, "hold")
        state = self.run_turn(s, state, "consume")
        self.assertEqual(state["values"], {"free": 2, "used": 4, "project": 0})
        state = self.run_turn(s, state)
        self.assertEqual(state["values"], {"free": 4, "used": 2, "project": 0})

    def test_oversubscription_is_order_independent(self):
        s = scenario()
        for order in (("hold", "spend"), ("spend", "hold")):
            state = self.run_turn(s, runner.initialize(s), *order)
            self.assertEqual(state["values"], s["initial"])
            self.assertEqual([r["fulfillment"] for r in state["requests"]],
                             ["allocation_conflict", "allocation_conflict"])
            self.assertEqual(state["ledger"], [])

    def test_same_commitment_collision(self):
        s = scenario()
        state = self.run_turn(s, runner.initialize(s), "hold", "hold")
        self.assertEqual(state["values"], s["initial"])
        self.assertTrue(all(r["fulfillment"] == "commitment_conflict" for r in state["requests"]))

    def test_release_cannot_fund_same_batch(self):
        s = scenario()
        state = self.run_turn(s, runner.initialize(s), "hold")
        state = self.run_turn(s, state, "release", "spend")
        self.assertEqual(state["values"], s["initial"])
        self.assertEqual(state["requests"][-1]["fulfillment"], "allocation_conflict")

    def test_recovery_does_not_touch_reserved_capacity(self):
        s = scenario()
        state = self.run_turn(s, runner.initialize(s), "hold")
        state = self.run_turn(s, state)
        self.assertEqual(state["values"], {"free": 2, "used": 0, "project": 4})

    def test_reject_invalid_authority_balance_and_external_writer(self):
        for mutation in ("owner", "balance", "event"):
            s = scenario()
            if mutation == "owner":
                s["actors"]["other"] = {"label": "Other", "visible_keys": []}
                s["action_catalog"]["hold"]["actors"] = ["other"]
            elif mutation == "balance":
                s["initial"]["free"] += 1
            else:
                s["events"] = [{"id": "bad", "minute": 10, "key": "free", "delta": 1}]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                runner.initialize(s)

    def test_checkpoint_tampering_rejected(self):
        s = scenario()
        state = self.run_turn(s, runner.initialize(s), "hold")
        bad = copy.deepcopy(state)
        bad["values"]["free"] += 1
        with self.assertRaises(ValueError):
            runner.verify_checkpoint(s, bad)

    def test_actor_local_brief_and_pending_warning(self):
        from age_runtime.core.observations import observe
        from age_runtime.core.decision_support import decision_brief
        s = scenario()
        s["actors"]["other"] = {"label": "Other", "visible_keys": []}
        state = runner.initialize(s)
        for action in ("hold", "spend"):
            state = runner.submit_request(s, state, "deity", {"action": action})
        own = decision_brief(observe(s, state, "deity"))["reserve_accounts"]["pr"]
        self.assertEqual(own["available"], 6)
        self.assertEqual(own["pending_gross_allocations"], 8)
        self.assertTrue(own["pending_overallocation"])
        self.assertEqual(observe(s, state, "other")["reserve_accounts"], {})

    def test_model_actor_uses_same_accounting(self):
        s = scenario()
        s["model_factions"] = ["deity"]
        state = runner.initialize(s)
        packet = runner.faction_packet(s, state, "deity")
        state = runner.accept_faction_choice(s, state, "deity", packet,
                                            {"packet_id": packet["packet_id"], "action": "hold"})
        state = runner.advance(s, state)
        runner.verify_checkpoint(s, state)
        self.assertEqual(state["values"]["project"], 4)
