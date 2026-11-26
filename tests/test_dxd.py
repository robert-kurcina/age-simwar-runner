import unittest
from age_runtime.core import dxd

class DXDTests(unittest.TestCase):
    def test_attributes(self):
        self.assertEqual([dxd.attribute_dm(n) for n in range(4, 13)],
                         [-2, -1, -1, 0, 1, 1, 2, 2, 3])

    def test_fixed_seed_and_flattening(self):
        a = dxd.test(42, dm=2, bonus=2, penalty=2)
        self.assertEqual(a, dxd.test(42, dm=2))
        self.assertEqual(len(a["active"]["kept"]), 2)

    def test_bonus_penalty_favor(self):
        normal = dxd.test(42)
        bonus = dxd.test(42, bonus=1)
        penalty = dxd.test(42, penalty=1)
        favor = dxd.test(42, favor=1)
        self.assertGreaterEqual(bonus["active"]["score"], normal["active"]["score"])
        self.assertLessEqual(penalty["active"]["score"], normal["active"]["score"])
        self.assertEqual(len(favor["active"]["kept"]), 3)

    def test_narrative_adversity(self):
        a = dxd.test(42, dm=2, narrative=True, adversity=1, adversity_dice=1, npc_dm=2)
        self.assertEqual(a["tn"], 13)
        self.assertEqual(a["active"], dxd.test(42, dm=2)["active"])
        with self.assertRaises(ValueError):
            dxd.test(42, narrative=True, penalty=1)

    def test_degrees(self):
        a = dxd.test(42, tn=1, dm=20)
        self.assertEqual(a["dos"], a["margin"] // 5)
        b = dxd.test(42, tn=40)
        self.assertEqual(b["dof"], -b["margin"] // 5)

    def test_opposed_tie_and_cancellation(self):
        for seed in range(100):
            a = dxd.opposed(seed, active_raw=7, target_raw=8, active_dm=1)
            if a["margin"] == 0:
                self.assertFalse(a["passed"])
                break
        else:
            self.fail("no tie")
        self.assertEqual(dxd.opposed(42, active_raw=7, target_raw=7,
                                     active_bonus=1, target_bonus=1),
                         dxd.opposed(42, active_raw=7, target_raw=7))

    def test_favor_policy(self):
        self.assertEqual(dxd.automatic_favor(available=1, maximum=2,
                         significance="critical", desired={"critical": 3}), 1)
        self.assertEqual(dxd.automatic_favor(available=4, maximum=2,
                         significance="routine", desired={"critical": 3}), 0)
