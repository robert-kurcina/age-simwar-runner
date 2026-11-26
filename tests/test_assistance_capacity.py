import json
from pathlib import Path
import unittest
from age_runtime.core.runner import initialize, advance, submit_request, verify_checkpoint

ROOT = Path(__file__).resolve().parents[1]


class AssistanceCapacityTest(unittest.TestCase):
    def scenario(self):
        s = json.loads((ROOT / "campaigns/civic-recovery/community-assistance.json").read_text())
        s["events"] = []
        s["initial"]["aid_packages"] = 4
        s["end_minute"] = 1440
        s["assistance_capacity"] = {"household_limit": 17, "households_per_package": 8}
        return s

    def test_finite_demand_and_partial_final_package(self):
        s = self.scenario()
        state = initialize(s)
        for _ in range(4):
            state = submit_request(s, state, "coordinator", {"action": "deliver_aid"})
            state = advance(s, state)
        self.assertEqual(state["values"]["households_assisted"], 17)
        self.assertEqual(state["values"]["aid_packages"], 1)
        self.assertEqual(state["requests"][-1]["fulfillment"], "all_households_assisted")
        verify_checkpoint(s, state)

    def test_invalid_capacity_and_scheduled_assistance(self):
        for cap in ({"household_limit": 0, "households_per_package": 8},
                    {"household_limit": 17, "households_per_package": True},
                    {"household_limit": 17}, None):
            s = self.scenario()
            s["assistance_capacity"] = cap
            with self.assertRaises(ValueError):
                initialize(s)
        s = self.scenario()
        s["initial"]["households_assisted"] = 18
        with self.assertRaises(ValueError):
            initialize(s)
        s = self.scenario()
        s["events"] = [{"id": "unbounded", "minute": 360, "key": "households_assisted", "delta": 18}]
        with self.assertRaises(ValueError):
            initialize(s)

    def test_no_packages_no_assistance(self):
        s = self.scenario()
        s["initial"]["aid_packages"] = 0
        state = advance(s, submit_request(s, initialize(s), "coordinator", {"action": "deliver_aid"}))
        self.assertEqual(state["values"]["households_assisted"], 0)
        self.assertEqual(state["requests"][0]["fulfillment"], "insufficient_packages")
        verify_checkpoint(s, state)
