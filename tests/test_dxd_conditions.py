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

    def test_sleep_limit_index_and_floor(self):
        from age_runtime.core.dxd_character import sleep_limit_hours
        self.assertEqual([sleep_limit_hours(7, w) for w in range(8)], [45, 35, 25, 20, 15, 10, 7, 7])
        self.assertEqual(sleep_limit_hours(11, 1), 95)
        self.assertEqual(sleep_limit_hours(7, 1, 2), 20)
        self.assertEqual(sleep_limit_hours(7, 0, 6), 7)

    def test_sleep_limit_no_retroactive_deprivation(self):
        from age_runtime.core.dxd import ATTRIBUTES
        attrs = dict.fromkeys(ATTRIBUTES, 7)
        clock = c.activity_initial(attrs, awake_seconds=40 * 3600)
        c.add(self.s, weariness=9, stress=14)
        c.refresh_sleep_limit(self.s, clock, attrs)
        self.assertEqual(clock["limit_seconds"], 20 * 3600)
        self.assertEqual(clock["overdue_seconds"], 0)
        c.advance_activity(self.s, clock, 3599, "active", attributes=attrs)
        self.assertEqual(self.s["weariness"], 11)
        c.advance_activity(self.s, clock, 1, "active", attributes=attrs)
        self.assertEqual(self.s["weariness"], 12)
        self.assertEqual(clock["limit_seconds"], 20 * 3600)
        self.assertEqual(clock["overdue_seconds"], 0)

    def test_recovery_recalculates_limit_and_resets_overdue(self):
        from age_runtime.core.dxd import ATTRIBUTES
        attrs = dict.fromkeys(ATTRIBUTES, 7)
        c.add(self.s, weariness=14)
        clock = c.activity_initial(attrs, awake_seconds=40 * 3600)
        c.advance_activity(self.s, clock, 1800, "rest", attributes=attrs)
        self.assertEqual(clock["overdue_seconds"], 1800)
        c.advance_activity(self.s, clock, 1800, "rest", attributes=attrs)
        # Simultaneous full overdue hour and rest recovery: recovery first,
        # then the one elapsed hour penalty; no retroactive penalties.
        self.assertEqual(self.s["weariness"], 11)
        self.assertEqual(clock["limit_seconds"], 35 * 3600)
        self.assertEqual(clock["overdue_seconds"], 0)

    def test_sleep_limit_split_invariance(self):
        import copy
        from age_runtime.core.dxd import ATTRIBUTES
        attrs = dict.fromkeys(ATTRIBUTES, 7)
        c.add(self.s, weariness=2, stress=14)
        clock = c.activity_initial(attrs, awake_seconds=30 * 3600)
        other, other_clock = copy.deepcopy(self.s), copy.deepcopy(clock)
        c.advance_activity(self.s, clock, 7200, "active", attributes=attrs)
        for seconds in (1200, 2000, 4000):
            c.advance_activity(other, other_clock, seconds, "active", attributes=attrs)
        self.assertEqual(self.s, other)
        self.assertEqual(clock, other_clock)

    def test_subdegree_concerns_do_not_reduce_limit(self):
        from age_runtime.core.dxd import ATTRIBUTES
        attrs = dict.fromkeys(ATTRIBUTES, 7)
        clock = c.activity_initial(attrs)
        c.add(self.s, weariness=9, stress=6)
        c.refresh_sleep_limit(self.s, clock, attrs)
        self.assertEqual(clock["limit_seconds"], 45 * 3600)

    def test_stress_recovery_mid_interval_restores_limit(self):
        from age_runtime.core.dxd import ATTRIBUTES
        attrs = dict.fromkeys(ATTRIBUTES, 7)
        c.add(self.s, stress=7)
        clock = c.activity_initial(attrs, awake_seconds=40 * 3600)
        c.advance_activity(self.s, clock, 1800, "quiet", safe=True, attributes=attrs)
        self.assertEqual(clock["limit_seconds"], 45 * 3600)
        self.assertEqual(clock["overdue_seconds"], 0)
        self.assertEqual(self.s["weariness"], 1)
