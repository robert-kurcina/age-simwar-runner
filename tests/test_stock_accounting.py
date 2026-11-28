"""Synthetic stock integration tests; no historical or economic calibration."""
import unittest

from age_runtime.core import runner
from age_runtime.core.observations import observe
from age_runtime.core.decision_support import decision_brief


def scenario():
    return {
        "version": 1, "id": "stock-test", "turn_minutes": 10, "end_minute": 80,
        "initial": {"a": 6, "b": 1, "c": 0},
        "events": [], "constraints": [],
        "actors": {"a": {"label": "A", "visible_keys": ["a"]},
                   "b": {"label": "B", "visible_keys": ["b", "c"]}},
        "action_catalog": {
            "give": {"description": "Give", "actors": ["a"]},
            "use": {"description": "Use", "actors": ["a"]},
            "return": {"description": "Return", "actors": ["b"]}},
        "stock_accounts": {
            "a": {"owner": "a", "key": "a", "unit": "grain"},
            "b": {"owner": "b", "key": "b", "unit": "grain"},
            "c": {"owner": "b", "key": "c", "unit": "wood"}},
        "stock_actions": {
            "give": {"source": "a", "destination": "b", "amount": 4, "purpose": "gift"},
            "use": {"source": "a", "destination": None, "amount": 3, "purpose": "consumption"},
            "return": {"source": "b", "destination": "a", "amount": 3, "purpose": "gift"}}}


class StockAccountingTests(unittest.TestCase):
    def turn(self, s, state, *orders):
        for actor, action in orders:
            state = runner.submit_request(s, state, actor, {"action": action})
        state = runner.advance(s, state)
        runner.verify_checkpoint(s, state)
        return state

    def test_transfer_conserves_stock_and_no_same_batch_credit(self):
        s = scenario()
        for orders in ((("a", "give"), ("b", "return")), (("b", "return"), ("a", "give"))):
            state = self.turn(s, runner.initialize(s), *orders)
            self.assertEqual(state["values"], {"a": 2, "b": 5, "c": 0})
            self.assertEqual(sum(state["values"].values()), 7)
            self.assertEqual(next(r for r in state["requests"] if r["actor"] == "b")["fulfillment"],
                             "stock_allocation_conflict")

    def test_oversubscription_rejects_all_debits(self):
        s = scenario()
        state = self.turn(s, runner.initialize(s), ("a", "give"), ("a", "use"))
        self.assertEqual(state["values"], s["initial"])
        self.assertFalse(state["ledger"])

    def test_loss_and_production_are_dated_and_bounded(self):
        s = scenario()
        s["stock_flows"] = [
            {"id": "harvest", "account": "a", "minute": 10, "kind": "production", "amount": 8, "basis": "fixture"},
            {"id": "spoilage", "account": "a", "minute": 10, "kind": "loss", "amount": 9, "basis": "fixture"}]
        state = self.turn(s, runner.initialize(s), ("a", "use"))
        self.assertEqual(state["values"]["a"], 8)
        self.assertEqual([e["delta"] for e in state["ledger"]], [-3, -3, 8])
        state = self.turn(s, state)
        self.assertEqual(state["values"]["a"], 8)

    def test_invalid_units_owner_and_external_writer(self):
        for kind in ("unit", "owner", "event"):
            s = scenario()
            if kind == "unit":
                s["stock_actions"]["give"]["destination"] = "c"
            elif kind == "owner":
                s["action_catalog"]["give"]["actors"] = ["b"]
            else:
                s["events"] = [{"id": "bad", "minute": 10, "key": "a", "delta": 1}]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                runner.initialize(s)

    def test_private_brief(self):
        s = scenario()
        state = runner.initialize(s)
        for action in ("give", "use"):
            state = runner.submit_request(s, state, "a", {"action": action})
        brief = decision_brief(observe(s, state, "a"))["stock_accounts"]
        self.assertEqual(set(brief), {"a"})
        self.assertTrue(brief["a"]["pending_overallocation"])
        self.assertEqual(set(observe(s, state, "b")["stock_accounts"]), {"b", "c"})

    def test_coexists_with_reserve_accounts(self):
        s = scenario()
        s["initial"].update(free=6, depleted=0)
        s["actors"]["a"]["visible_keys"].extend(["free", "depleted"])
        s["reserve_accounts"] = {"pr": {"owner": "a", "capacity": 6, "available": "free",
                                        "depleted": "depleted", "commitments": {}, "recovery": 2}}
        s["reserve_actions"] = {"divine": {"account": "pr", "operation": "spend",
                                          "amount": 4, "commitment": None}}
        s["action_catalog"]["divine"] = {"description": "Divine", "actors": ["a"]}
        state = self.turn(s, runner.initialize(s), ("a", "use"), ("a", "divine"))
        self.assertEqual(state["values"], {"a": 3, "b": 1, "c": 0, "free": 2, "depleted": 4})
        s["stock_accounts"]["a"]["key"] = "free"
        with self.assertRaises(ValueError):
            runner.initialize(s)

    def test_model_stock_choice(self):
        s = scenario()
        s["model_factions"] = ["b"]
        state = runner.initialize(s)
        packet = runner.faction_packet(s, state, "b")
        state = runner.accept_faction_choice(s, state, "b", packet,
                                             {"packet_id": packet["packet_id"], "action": "return"})
        state = runner.advance(s, state)
        runner.verify_checkpoint(s, state)
        self.assertEqual(state["values"]["b"], 1)
        self.assertEqual(state["requests"][0]["fulfillment"], "stock_allocation_conflict")
