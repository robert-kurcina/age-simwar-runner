import copy
import json
import unittest
from pathlib import Path
from runner import initialize, advance, verify_checkpoint, submit_request, save
from observations import observe
from actions import register_request, validate_request

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
        library["objectives"]["access"]["met"] = True
        self.assertTrue(state["actors"]["library"]["objectives"]["access"]["met"])

    def test_hidden_objective_is_not_a_side_channel(self):
        self.s["actors"]["library"]["objectives"]["hidden"] = {
            "key": "inspection_notes", "comparison": "equal",
            "threshold": 1, "description": "Private note"}
        state = initialize(self.s)
        self.assertNotIn("hidden", observe(self.s, state, "library")["objectives"])

    def test_default_deny_and_unknown_actor(self):
        del self.s["actors"]["library"]["visible_keys"]
        self.s["actors"]["library"].pop("report_delay_minutes", None)
        state = initialize(self.s)
        self.assertEqual(observe(self.s, state, "library")["values"], {})
        with self.assertRaises(ValueError):
            observe(self.s, state, "missing")

    def test_invalid_visibility(self):
        self.s["actors"]["library"]["visible_keys"] = ["missing"]
        with self.assertRaises(ValueError):
            initialize(self.s)

    def test_request_registration_is_pure(self):
        state = initialize(self.s)
        original = copy.deepcopy(state)
        record = register_request(self.s, state, "library", {"action": "request_room_inspection"})
        self.assertEqual(record["status"], "validated_request")
        self.assertEqual(record["minute"], 0)
        self.assertEqual(state, original)

    def test_request_rejects_actor_override_and_unlisted_action(self):
        with self.assertRaises(ValueError):
            validate_request(self.s, "library", {"action": "request_room_inspection", "actor": "maintenance"})
        with self.assertRaises(ValueError):
            validate_request(self.s, "library", {"action": "request_maintenance_review"})
        with self.assertRaises(ValueError):
            validate_request(self.s, "library", {"action": "unknown"})

    def test_actor_request_projection(self):
        state = initialize(self.s)
        self.assertNotIn("request_maintenance_review", observe(self.s, state, "library")["available_requests"])
        self.assertIn("request_maintenance_review", observe(self.s, state, "maintenance")["available_requests"])

    def test_ended_session_rejects_requests(self):
        state = advance(self.s, advance(self.s, initialize(self.s)))
        self.assertEqual(observe(self.s, state, "library")["available_requests"], {})
        with self.assertRaises(ValueError):
            register_request(self.s, state, "library", {"action": "request_room_inspection"})

    def test_catalog_rejects_unknown_actor(self):
        self.s["action_catalog"]["request_room_inspection"]["actors"] = ["unknown"]
        with self.assertRaises(ValueError):
            initialize(self.s)

    def test_persistent_request_replay(self):
        a = initialize(self.s)
        b = submit_request(self.s, a, "library", {"action": "request_room_inspection"})
        self.assertEqual(a["requests"], [])
        self.assertEqual(a["values"], b["values"])
        c = advance(self.s, b)
        d = submit_request(self.s, c, "maintenance", {"action": "request_maintenance_review"})
        self.assertEqual([r["sequence"] for r in d["requests"]], [1, 2])
        verify_checkpoint(self.s, d)
        self.assertEqual(len(observe(self.s, d, "library")["own_requests"]), 1)
        self.assertEqual(len(observe(self.s, d, "maintenance")["own_requests"]), 1)
        self.assertNotIn("sequence", observe(self.s, d, "maintenance")["own_requests"][0])

    def test_request_replay_rejects_altered_metadata(self):
        state = submit_request(self.s, initialize(self.s), "library", {"action": "request_room_inspection"})
        for field, value in [("minute", 1), ("sequence", 8), ("status", "executed"), ("turn", False)]:
            altered = copy.deepcopy(state)
            altered["requests"][0][field] = value
            with self.assertRaises(ValueError):
                verify_checkpoint(self.s, altered)

    def test_request_checkpoint_round_trip(self):
        import tempfile
        state = submit_request(self.s, initialize(self.s), "library", {"action": "request_room_inspection"})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            save(path, state)
            restored = json.loads(path.read_text())
            verify_checkpoint(self.s, restored)
            self.assertEqual(state, restored)

    def test_delayed_reports_and_objectives(self):
        a = initialize(self.s)
        view = observe(self.s, a, "library")
        self.assertEqual(view["reports"]["available_rooms"], {"status": "unknown"})
        self.assertNotIn("available_rooms", view["values"])
        self.assertNotIn("access", view["objectives"])
        b = advance(self.s, a)
        view = observe(self.s, b, "library")
        self.assertEqual(b["values"]["available_rooms"], 5)
        self.assertEqual(view["values"]["available_rooms"], 2)
        self.assertEqual(view["reports"]["available_rooms"]["as_of_minute"], 300)
        self.assertEqual(view["reports"]["available_rooms"]["status"], "stale")
        self.assertFalse(view["objectives"]["access"]["met"])
        self.assertTrue(b["actors"]["library"]["objectives"]["access"]["met"])
        c = advance(self.s, b)
        self.assertEqual(observe(self.s, c, "library")["values"]["available_rooms"], 5)

    def test_current_report(self):
        state = advance(self.s, initialize(self.s))
        view = observe(self.s, state, "maintenance")
        self.assertEqual(view["reports"]["available_rooms"]["status"], "current")
        self.assertEqual(view["values"]["available_rooms"], 5)

    def test_invalid_delay(self):
        for bad in [{"available_rooms": -1}, {"inspection_notes": 10}, {"available_rooms": True}]:
            self.s["actors"]["library"]["report_delay_minutes"] = bad
            with self.assertRaises(ValueError):
                initialize(self.s)

    def test_checkpoint_version_and_identity(self):
        state = initialize(self.s)
        for version in [None, True, 2]:
            bad = copy.deepcopy(state)
            bad["checkpoint_version"] = version
            with self.assertRaisesRegex(ValueError, "unsupported checkpoint version"):
                verify_checkpoint(self.s, bad)
        revised = copy.deepcopy(self.s)
        revised["id"] = "revised"
        with self.assertRaisesRegex(ValueError, "scenario revision mismatch"):
            verify_checkpoint(revised, state)

    def test_inspect_is_read_only(self):
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "session.json"
            state = initialize(self.s)
            save(path, state)
            before = path.read_bytes()
            root = Path(__file__).parent
            result = subprocess.run(
                [sys.executable, str(root / "runner.py"),
                 str(root / "scenarios/demo.json"), str(path),
                 "--inspect", "--actor", "library"],
                capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)["turn"], 0)
            self.assertEqual(path.read_bytes(), before)

    def test_duplicate_event(self):
        self.s["events"].append(copy.deepcopy(self.s["events"][0]))
        with self.assertRaises(ValueError):
            initialize(self.s)

if __name__ == "__main__":
    unittest.main()
