import unittest
import copy
from age_runtime.core import dxd_injury
from age_runtime.mythos import mythos, medical


class MedicalTests(unittest.TestCase):
    def patient(self, amount=3):
        state = mythos.initial("boothbay", 42)
        state["location"] = state["npcs"]["eleanor"]["location"]
        dxd_injury.apply(state["dxd"]["injury"], amount)
        return state

    def schedule(self, state):
        return mythos.establish_step(state, {"medical_bandage": {
            "npc": "eleanor", "basis": "Eleanor agrees to apply an available bandage."}})

    def test_treatment_requires_elapsed_time_and_consumes_supply(self):
        state = self.patient()
        before = copy.deepcopy(state)
        after = self.schedule(state)
        self.assertEqual(state, before)
        self.assertEqual(after["medical_supplies"]["eleanor"], 1)
        self.assertEqual(after["dxd"]["injury"]["injury"], 3)
        self.assertIsNotNone(medical.pending(after))
        with self.assertRaises(ValueError):
            self.schedule(after)
        after = mythos.step(after, "observe")
        self.assertEqual(after["dxd"]["injury"]["injury"], 2)
        self.assertIsNone(medical.pending(after))
        self.assertEqual(after["timed_detail_events"][-1]["status"], "completed")

    def test_incapacitated_patient_can_receive_treatment(self):
        state = self.patient(13)
        self.assertEqual(dxd_injury.projection(state["dxd"]["injury"])["status"], "coma")
        state = self.schedule(state)
        state = mythos.step(state, "await_assistance")
        self.assertEqual(state["dxd"]["injury"]["injury"], 12)
        self.assertIsNone(medical.pending(state))

    def test_interrupted_treatment_not_refunded(self):
        state = self.schedule(self.patient())
        _, rules = mythos.load("boothbay")
        medical.interrupt_unavailable(state, rules, mythos.npc_available, moving=True)
        self.assertIsNone(medical.pending(state))
        self.assertEqual(state["medical_supplies"]["eleanor"], 1)
        self.assertEqual(state["dxd"]["injury"]["injury"], 3)

    def test_dying_latch_and_dead_patient(self):
        state = self.patient(24)
        injury = state["dxd"]["injury"]
        injury["injury"] -= 1
        self.assertEqual(dxd_injury.projection(injury)["status"], "dying")
        dxd_injury.apply(injury, 36)
        with self.assertRaises(ValueError):
            self.schedule(state)
