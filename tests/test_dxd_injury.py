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


    def test_dedicated_thresholds_and_partitioned_deterioration(self):
        state = dxd_injury.initial(12, 12, 4)
        for incoming, status in ((12, "severely_injured"), (13, "coma"), (24, "dying")):
            dxd_injury.apply(state, incoming)
            self.assertEqual(dxd_injury.projection(state)["status"], status)
        whole = copy.deepcopy(state)
        dxd_injury.advance(state, 239)
        self.assertEqual(state["injury"], 24)
        dxd_injury.advance(state, 241)
        dxd_injury.advance(whole, 480)
        self.assertEqual(state, whole)
        self.assertEqual(state["injury"], 26)
        self.assertEqual(dxd_injury.advance(state, 99999), 2400)
        self.assertEqual(dxd_injury.projection(state)["status"], "dead")

    def test_incapacity_blocks_voluntary_actions_and_advances_clock(self):
        state = mythos.initial("boothbay", 42)
        injury = state["dxd"]["injury"]
        dxd_injury.apply(injury, injury["capacity"] + injury["size"])
        self.assertEqual([a["id"] for a in mythos.view(state)["choices"]], ["await_assistance"])
        with self.assertRaises(ValueError):
            mythos.step(state, "observe")
        before = copy.deepcopy(state)
        after = mythos.step(state, "await_assistance")
        self.assertEqual(state, before)
        self.assertEqual(after["dxd"]["injury"]["injury"], injury["injury"] + 1)
        self.assertNotEqual(after["time"], state["time"])
        self.assertEqual(after["dxd"]["concerns"], state["dxd"]["concerns"])
