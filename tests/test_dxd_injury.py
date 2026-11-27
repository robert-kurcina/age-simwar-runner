import unittest
import copy
from age_runtime.core import dxd_injury
from age_runtime.mythos import mythos, beats


class InjuryTests(unittest.TestCase):
    def test_native_threshold_and_status(self):
        state = dxd_injury.initial(12)
        for incoming, expected in ((4, 4), (6, 6), (5, 7), (2, 8)):
            dxd_injury.apply(state, incoming)
            self.assertEqual(state["injury"], expected)
        self.assertEqual(dxd_injury.penalty_dice(state), 1)
        dxd_injury.apply(state, 12)
        self.assertEqual(dxd_injury.projection(state)["status"], "dying")
        self.assertEqual(dxd_injury.projection(state)["bodypoints"], 0)

    def test_optional_capacity_and_projection(self):
        state = mythos.initial("boothbay", 42)
        self.assertEqual(mythos.view(state)["condition"]["physical_injury"]["status"], "uninjured")
        self.assertEqual(state["dxd"]["injury"]["capacity"], state["dxd"]["body"]["physical"]["bodypoints"])
        mythos.verify(state)
        mythos.verify(mythos.step(state, "observe"))

    def test_reviewed_beat_injury_and_guard(self):
        _, rules = mythos.load("boothbay")
        rules = copy.deepcopy(rules)
        state = mythos.initial("boothbay", 42)
        state["location"] = "Creek Inlet South"
        state["flags"].append("filament_anomaly")
        key = "beat:inlet_withdrawal"
        rules["danger_beats"][key]["resolved_injury_on_dof"] = 6
        request = {"action": key, "approach": "careful_footing", "intent": "Withdraw."}
        action = beats.compile_beat(state, rules, request)
        beats.record(state, rules, action, {"passed": False, "dof": 1})
        self.assertEqual(state["dxd"]["injury"]["injury"], 6)
        before = copy.deepcopy(state)
        beats.record(state, rules, action, {"passed": True, "dos": 0})
        self.assertEqual(state["dxd"]["injury"], before["dxd"]["injury"])
        rules["danger_beats"][key]["resolved_injury_on_dof"] = 12
        with self.assertRaises(ValueError):
            beats.compile_beat(state, rules, request)
