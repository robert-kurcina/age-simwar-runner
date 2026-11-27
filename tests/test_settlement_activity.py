"""Settlement context is bounded, private and mechanically neutral."""
import copy
import unittest
from age_runtime.mythos import mythos, settlement_activity


class SettlementActivityTests(unittest.TestCase):
    def test_calendar_and_zone_context(self):
        _, rules = mythos.load("boothbay")
        state = mythos.initial("boothbay", 42)
        for location, at, level in (
            ("Harbor Docks", "1927-10-13T12:00:00", "busy"),
            ("Harbor Docks", "1927-10-15T03:00:00", "quiet"),
            ("Harbor Diner", "1927-10-16T12:00:00", "ordinary"),
            ("Creek Inlet South", "1927-10-13T12:00:00", "sparse"),
            ("Devil's Throat Sea Caves", "1927-10-13T12:00:00", "quiet"),
        ):
            state["location"], state["time"] = location, at
            before = copy.deepcopy(state)
            context = settlement_activity.projection(state, rules)
            self.assertEqual(context["level"], level)
            self.assertEqual(context["authority"], "ambience_only")
            self.assertEqual(state, before)

    def test_private_projection_and_replay(self):
        state = mythos.initial("boothbay", 42)
        before = copy.deepcopy(state)
        context = mythos.gm_context(state, compact=True)["referee"]["settlement_activity"]
        self.assertEqual(context["level"], "busy")
        self.assertNotIn("settlement_activity", mythos.view(state))
        self.assertEqual(state, before)
        mythos.verify(state)
        state = mythos.step(state, "observe")
        mythos.verify(state)

    def test_validation_and_inheritance(self):
        _, rules = mythos.load("boothbay")
        settlement_activity.validate(rules)
        state = mythos.initial("boothbay", 42)
        cfg = copy.deepcopy(rules)
        cfg["settlement_activity"]["boothbay"] = cfg["settlement_activity"].pop("town")
        self.assertEqual(settlement_activity.projection(state, cfg)["zone"], "boothbay")
        cfg["settlement_activity"]["boothbay"]["windows"].append(
            copy.deepcopy(cfg["settlement_activity"]["boothbay"]["windows"][0]))
        with self.assertRaises(ValueError):
            settlement_activity.validate(cfg)

    def test_legacy_without_activity(self):
        _, rules = mythos.load("boothbay")
        rules = copy.deepcopy(rules)
        del rules["settlement_activity"]
        settlement_activity.validate(rules)
        self.assertIsNone(settlement_activity.projection(mythos.initial("boothbay", 42), rules))
