import unittest
from age_runtime.core import dxd_conditions as c

class DXDConcernTests(unittest.TestCase):
    def setUp(self):
        from age_runtime.core.dxd import ATTRIBUTES
        self.s = c.initial(dict.fromkeys(ATTRIBUTES, 7))

    def test_thresholds_and_weariness(self):
        self.assertEqual(self.s["capacity"], {"endurance": 10, "resilience": 7, "recovery_rate": 4})
        c.add(self.s, fatigue=9, stress=6)
        self.assertEqual(self.s["weariness"], 0)
        c.add(self.s, fatigue=11, stress=1)
        self.assertEqual(self.s["weariness"], 3)
        self.assertEqual(c.penalty_dice(self.s), 2)
        self.assertEqual(c.penalty_dice(self.s, decision=True), 3)

    def test_recovery_and_no_duplicate_degrees(self):
        c.add(self.s, fatigue=10, stress=7)
        c.add(self.s)
        self.assertEqual(self.s["weariness"], 2)
        c.recover(self.s, 10, restful=True, safe=False)
        self.assertEqual(self.s["fatigue"], 6)
        self.assertEqual(self.s["stress"], 7)
        c.recover(self.s, 60, restful=True, safe=True)
        self.assertEqual(c.degrees(self.s), {"fatigue": 0, "stress": 0, "weariness": 0})
        self.assertEqual(self.s["weariness"], 0)
