"""Approach-specific danger consequences use existing native resolution."""
import copy
import unittest
from unittest.mock import patch

from age_runtime.mythos import mythos, beats


class DangerApproachTests(unittest.TestCase):
    def fixture(self):
        story, rules = mythos.load("boothbay")
        rules = copy.deepcopy(rules)
        return story, rules

    def request(self, approach):
        return {"action": "beat:patrol_approach", "approach": approach,
                "intent": "Resolve the reviewed objective."}

    def test_withdrawal_does_not_grant_passage(self):
        story, rules = self.fixture()
        with patch.object(mythos, "load", return_value=(story, rules)):
            for seed in range(12):
                state = mythos.initial("boothbay", seed)
                state["location"] = "Lighthouse (Western Point)"
                state["flags"].extend(["patrol_risk", "written_account"])
                before = copy.deepcopy(state)
                request = self.request("withdraw")
                after = mythos.step(state, request["action"], request)
                self.assertEqual(state, before)
                self.assertIn("patrol_withdrawn", after["flags"])
                self.assertNotIn("patrol_passage", after["flags"])
                self.assertNotIn("account_relayed", after["flags"])
                self.assertNotIn("patrol_blocked", after["flags"])
                self.assertEqual(after["time"], "1927-10-13T08:01:00")
                self.assertFalse(any(x["action"] == request["action"] for x in beats.available(after, rules)))

    def test_approach_prerequisites_and_completion(self):
        story, rules = self.fixture()
        spec = rules["danger_beats"]["beat:patrol_approach"]["approaches"]["withdraw"]
        spec["requires_flags"] = ["shelter_known"]
        spec["excludes_flags"] = ["shelter_closed"]
        with patch.object(mythos, "load", return_value=(story, rules)):
            state = mythos.initial("boothbay", 42)
            state["location"] = "Lighthouse (Western Point)"
            state["flags"].extend(["patrol_risk", "written_account"])
            request = self.request("withdraw")
            with self.assertRaises(ValueError):
                beats.compile_beat(state, rules, request)
            state["flags"].append("shelter_known")
            action = beats.compile_beat(state, rules, request)
            self.assertTrue(beats.completion_available(state, rules, action))
            state["flags"].append("shelter_closed")
            self.assertFalse(beats.completion_available(state, rules, action))
            other = beats.compile_beat(state, rules, self.request("quiet_approach"))
            self.assertEqual(other["grant"], ["patrol_passage"])
            self.assertEqual(other["grant_failure"], ["patrol_blocked"])
