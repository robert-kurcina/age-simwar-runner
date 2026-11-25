import copy
import json
import unittest
from pathlib import Path
from runner import initialize, advance, verify_checkpoint
from observations import observe

class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.s = json.loads((Path(__file__).parent / "scenarios/demo.json").read_text())

    def test_subturn_and_boundary(self):
        a = initialize(self.s)
        b = advance(self.s, a)
        self.assertEqual(a["values"]["available_rooms"], 0)
        self.assertEqual(b["minute"], 360)
        self.assertEqual(b["values"]["available_rooms"], 5)
        self.assertEqual(len(b["ledger"]), 2)
        self.assertTrue(all(c["passed"] for c in b["checks"]))
        c = advance(self.s, b)
        self.assertEqual(len(c["ledger"]), 2)
        self.assertEqual(advance(self.s, c), c)
        verify_checkpoint(self.s, c)

    def test_failed_constraint_is_not_forced(self):
        self.s["constraints"][0]["equals"] = 99
        b = advance(self.s, initialize(self.s))
        self.assertFalse(b["checks"][0]["passed"])
        self.assertEqual(b["values"]["available_rooms"], 5)

    def test_changed_scenario(self):
        a = initialize(self.s)
        self.s["turn_minutes"] = 120
        with self.assertRaises(ValueError):
            advance(self.s, a)

    def test_tampered_checkpoint(self):
        a = advance(self.s, initialize(self.s))
        a["values"]["available_rooms"] += 1
        with self.assertRaises(ValueError):
            verify_checkpoint(self.s, a)

    def test_actor_objectives(self):
        a = initialize(self.s)
        b = advance(self.s, a)
        self.assertFalse(a["actors"]["library"]["objectives"]["access"]["met"])
        self.assertTrue(b["actors"]["library"]["objectives"]["access"]["met"])
        verify_checkpoint(self.s, b)

    def test_unknown_objective_variable(self):
        self.s["actors"]["library"]["objectives"]["access"]["key"] = "missing"
        with self.assertRaises(ValueError):
            initialize(self.s)

    def test_actor_projection(self):
        state = advance(self.s, initialize(self.s))
        library = observe(self.s, state, "library")
        maintenance = observe(self.s, state, "maintenance")
        self.assertNotIn("inspection_notes", library["values"])
        self.assertIn("inspection_notes", maintenance["values"])
        self.assertNotIn("ledger", library)
        self.assertNotIn("checks", library)
        self.assertNotIn("actors", library)
        library["objectives"]["access"]["met"] = False
        self.assertTrue(state["actors"]["library"]["objectives"]["access"]["met"])

    def test_hidden_objective_is_not_a_side_channel(self):
        self.s["actors"]["library"]["objectives"]["hidden"] = {
            "key": "inspection_notes", "comparison": "equal",
            "threshold": 1, "description": "Private note"}
        state = initialize(self.s)
        self.assertNotIn("hidden", observe(self.s, state, "library")["objectives"])

    def test_default_deny_and_unknown_actor(self):
        del self.s["actors"]["library"]["visible_keys"]
        state = initialize(self.s)
        self.assertEqual(observe(self.s, state, "library")["values"], {})
        with self.assertRaises(ValueError):
            observe(self.s, state, "missing")

    def test_invalid_visibility(self):
        self.s["actors"]["library"]["visible_keys"] = ["missing"]
        with self.assertRaises(ValueError):
            initialize(self.s)

    def test_duplicate_event(self):
        self.s["events"].append(copy.deepcopy(self.s["events"][0]))
        with self.assertRaises(ValueError):
            initialize(self.s)

if __name__ == "__main__":
    unittest.main()
