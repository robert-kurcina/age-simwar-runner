import copy
import json
import unittest
from pathlib import Path
from age_runtime.core.runner import initialize, advance, verify_checkpoint
from age_runtime.core.observations import observe

class DependentEventsTests(unittest.TestCase):
    def setUp(self):
        self.s = json.loads((Path(__file__).resolve().parents[1] /
            "campaigns/civic-recovery/service-review.json").read_text())

    def test_ignored_report_assessed_and_replays(self):
        s = self.s
        a = initialize(s)
        b = advance(s, a)
        self.assertEqual(a["values"]["reports_assessed"], 0)
        self.assertEqual(b["values"]["reports_assessed"], 1)
        self.assertEqual(b["values"]["review_capacity"], 0)
        self.assertEqual(b["background_events"][0]["outcome"], "completed")
        self.assertTrue(observe(s, b, "reviewer")["objectives"]["assessment"]["met"])
        self.assertNotIn("background_events", observe(s, b, "reviewer"))
        self.assertEqual(advance(s, b), b)
        verify_checkpoint(s, b)

    def test_missing_report_or_capacity_prevents_assessment(self):
        for missing in ("report", "capacity"):
            s = copy.deepcopy(self.s)
            if missing == "report":
                s["events"] = []
            else:
                s["initial"]["review_capacity"] = 0
            b = advance(s, initialize(s))
            self.assertEqual(b["values"]["reports_assessed"], 0)
            self.assertEqual(b["background_events"][0]["outcome"], "prerequisite_unmet")
            self.assertEqual(b["values"]["review_capacity"], s["initial"]["review_capacity"])
            verify_checkpoint(s, b)

    def test_same_time_resource_contention_and_constraint_order(self):
        s = self.s
        e = copy.deepcopy(s["dependent_events"][0])
        e["id"] = "second-assessment"
        s["dependent_events"].append(e)
        s["constraints"] = [{"minute":360,"key":"reports_assessed","equals":1}]
        b = advance(s, initialize(s))
        self.assertEqual([x["outcome"] for x in b["background_events"]],
                         ["completed", "prerequisite_unmet"])
        self.assertTrue(b["checks"][0]["passed"])
        self.assertEqual(b["values"]["review_capacity"], 0)
        verify_checkpoint(s, b)

    def test_reject_hidden_delayed_or_unguarded_conditions(self):
        for kind in ("hidden", "delayed", "unguarded", "duplicate", "unknown"):
            s = copy.deepcopy(self.s)
            e = s["dependent_events"][0]
            if kind == "hidden":
                s["actors"]["reviewer"]["visible_keys"].remove("reports_received")
            elif kind == "delayed":
                s["actors"]["reviewer"]["report_delay_minutes"] = {"reports_received":1}
            elif kind == "unguarded":
                e["requires"].pop()
            elif kind == "duplicate":
                e["id"] = "report"
            else:
                e["participant"] = "missing"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                initialize(s)

    def test_tamper_rejected(self):
        b = advance(self.s, initialize(self.s))
        b["background_events"][0]["outcome"] = "prerequisite_unmet"
        with self.assertRaises(ValueError):
            verify_checkpoint(self.s, b)
