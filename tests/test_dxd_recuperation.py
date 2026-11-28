import unittest
from age_runtime.core import dxd_injury as injury


class RecuperationTests(unittest.TestCase):
    def patient(self, amount):
        state = injury.initial(12, 12, 4)
        injury.apply(state, amount)
        return state

    def test_general_interval_and_partition(self):
        state = self.patient(6)
        self.assertEqual(injury.recuperate(state, 29*injury.DAY, regime="general", eligible=True), 0)
        self.assertEqual(injury.recuperate(state, injury.DAY, regime="general", eligible=True), 4)
        self.assertEqual(state["injury"], 2)
        self.assertEqual(injury.recuperate(state, 30*injury.DAY, regime="general", eligible=True), 2)
        self.assertNotIn("recuperation", state)

    def test_severe_interval_and_reassessment(self):
        state = self.patient(10)
        self.assertEqual(injury.recuperate(state, 89*injury.DAY, regime="general", eligible=True), 0)
        self.assertEqual(injury.recuperate(state, 31*injury.DAY, regime="general", eligible=True), 8)
        self.assertEqual(state["injury"], 2)

    def test_interruption_and_regime_exclusion(self):
        state = self.patient(4)
        injury.recuperate(state, 6*injury.DAY, regime="post_battle", eligible=True)
        with self.assertRaises(ValueError):
            injury.recuperate(state, injury.DAY, regime="general", eligible=True)
        injury.recuperate(state, 1, regime="post_battle", eligible=False)
        self.assertEqual(injury.recuperate(state, injury.DAY, regime="post_battle", eligible=True), 0)
        self.assertEqual(state["injury"], 4)

    def test_post_dying_precedence(self):
        state = self.patient(24)
        with self.assertRaises(ValueError):
            injury.recuperate(state, 30*injury.DAY, regime="post_dying", eligible=True)
        # Simulate prior completed medical stabilization.
        state.update(injury=8, dying_latched=False, dying_seconds=0)
        with self.assertRaises(ValueError):
            injury.recuperate(state, 30*injury.DAY, regime="general", eligible=True)
        self.assertEqual(injury.recuperate(state, 30*injury.DAY, regime="post_dying", eligible=True), 1)
        self.assertEqual(state["injury"], 7)
