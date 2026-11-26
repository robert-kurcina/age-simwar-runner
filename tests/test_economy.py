import copy
import unittest
from age_runtime.core.economy import bottleneck
from age_runtime.core.runner import initialize, advance, verify_checkpoint
from age_runtime.core.observations import observe

def fixture():
    return {"version": 1, "id": "civilian-project-fixture", "turn_minutes": 10080,
            "end_minute": 40320, "initial": {"labor": 2, "finance": 3, "stage": 0,
            "delay": 0, "complications": 0}, "events": [
                {"id": "resources-arrive", "minute": 20160, "key": "labor", "delta": 1}],
            "constraints": [{"minute": 30240, "key": "stage", "equals": 2}],
            "actors": {"council": {"label": "Council", "visible_keys": [
                "labor", "finance", "stage", "delay", "complications"]},
                "other": {"label": "Other", "visible_keys": []}},
            "economy_projects": [{"id": "repair", "participant": "council", "need": 3,
                "axes": [{"axis": "labor", "key": "labor"}, {"axis": "finance", "key": "finance"}],
                "stages": 2, "progress": "stage", "delay": "delay", "complications": "complications"}]}

class EconomyTests(unittest.TestCase):
    def test_native_shortfall_bands_and_tie(self):
        for rating, outcome in enumerate(("scope_not_credible", "scope_not_credible", "stalled",
                                          "serious_delay", "minor_delay", "clear")):
            self.assertEqual(bottleneck(5, [("labor", rating)])["outcome"], outcome)
        self.assertEqual(bottleneck(3, [("finance", 1), ("labor", 1)])["axis"], "finance")
        self.assertIsNone(bottleneck(2, [("labor", 5)])["axis"])

    def test_delayed_then_completed_project_replay(self):
        s = fixture()
        a = initialize(s)
        b = advance(s, a)
        self.assertEqual(b["values"]["delay"], 1)
        self.assertEqual(b["values"]["stage"], 0)
        c = advance(s, b)
        self.assertEqual(c["values"]["stage"], 1)
        d = advance(s, c)
        self.assertEqual(d["values"]["stage"], 2)
        self.assertTrue(d["checks"][0]["passed"])
        e = advance(s, d)
        self.assertEqual(len(e["project_results"]), 3)
        self.assertEqual(observe(s, e, "other")["project_results"], [])
        self.assertEqual(observe(s, e, "council")["project_results"][-1]["outcome"], "clear")
        verify_checkpoint(s, e)
        e["project_results"][0]["outcome"] = "clear"
        with self.assertRaises(ValueError):
            verify_checkpoint(s, e)

    def test_serious_and_stalled(self):
        for rating, outcome, delay, complications in [(1, "serious_delay", 1, 1), (0, "stalled", 0, 0)]:
            s = fixture()
            s["initial"]["labor"] = rating
            b = advance(s, initialize(s))
            self.assertEqual(b["project_results"][0]["outcome"], outcome)
            self.assertEqual(b["values"]["stage"], 0)
            self.assertEqual(b["values"]["delay"], delay)
            self.assertEqual(b["values"]["complications"], complications)

    def test_invalid_capacity_visibility_and_counter_ownership(self):
        for kind in ("range", "future_range", "hidden", "delay", "counter", "mixed"):
            s = fixture()
            if kind == "range":
                s["initial"]["labor"] = 6
            elif kind == "future_range":
                s["events"][0]["delta"] = 4
            elif kind == "hidden":
                s["actors"]["council"]["visible_keys"].remove("labor")
            elif kind == "delay":
                s["actors"]["council"]["report_delay_minutes"] = {"labor": 1}
            elif kind == "counter":
                s["events"].append({"id":"bad","minute":10080,"key":"stage","delta":1})
            else:
                s["economy_projects"][0]["progress"] = "labor"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                initialize(s)
