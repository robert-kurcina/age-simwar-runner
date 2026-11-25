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
        for version in [None, True, 1, 3]:
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

    def test_bounded_review_resolution(self):
        a = initialize(self.s)
        b = submit_request(self.s, a, "library", {"action": "request_room_inspection"})
        b = submit_request(self.s, b, "maintenance", {"action": "request_maintenance_review"})
        c = advance(self.s, b)
        self.assertEqual(b["requests"][0]["status"], "validated_request")
        self.assertEqual(c["requests"][0]["status"], "reviewed")
        self.assertEqual(c["requests"][0]["reviewed_minute"], 360)
        self.assertEqual(c["requests"][1]["status"], "validated_request")
        self.assertEqual(c["values"], advance(self.s, a)["values"])
        verify_checkpoint(self.s, c)
        d = advance(self.s, c)
        self.assertEqual(d["requests"][1]["reviewed_minute"], 720)
        self.assertEqual(advance(self.s, d), d)
        verify_checkpoint(self.s, d)

    def test_zero_review_capacity(self):
        self.s["administrative_reviews_per_turn"] = 0
        a = submit_request(self.s, initialize(self.s), "library", {"action": "request_room_inspection"})
        b = advance(self.s, a)
        self.assertEqual(b["requests"][0]["status"], "validated_request")
        verify_checkpoint(self.s, b)

    def test_review_capacity_validation(self):
        for value in [-1, True, 1.5]:
            self.s["administrative_reviews_per_turn"] = value
            with self.assertRaises(ValueError):
                initialize(self.s)

    def test_consolidated_demo(self):
        from demo import run_demo
        result = run_demo()
        self.assertEqual(result, run_demo())
        self.assertEqual(result["timeline"], [
            {"turn": 0, "minute": 0, "actual_rooms": 0, "reported_rooms": None,
             "pending_reviews": 2, "reviewed": 0},
            {"turn": 1, "minute": 360, "actual_rooms": 5, "reported_rooms": 2,
             "pending_reviews": 1, "reviewed": 1},
            {"turn": 2, "minute": 720, "actual_rooms": 5, "reported_rooms": 5,
             "pending_reviews": 0, "reviewed": 2},
        ])
        self.assertTrue(result["constraints_passed"])
        self.assertTrue(result["final_objectives"]["library"]["objectives"]["access"]["met"])

    def test_interpretation_packet_is_actor_local(self):
        from interpretation import interpretation_packet, prompt
        state = advance(self.s, initialize(self.s))
        original = copy.deepcopy(state)
        packet = interpretation_packet(state, "library")
        self.assertEqual(packet["observation"]["reports"]["available_rooms"]["value"], 2)
        self.assertNotIn("inspection_notes", prompt(packet))
        self.assertNotIn("maintenance", prompt(packet))
        self.assertNotIn("available_requests", packet["observation"])
        self.assertEqual(state, original)

    def test_interpretation_response_is_commentary_only(self):
        from interpretation import interpretation_packet, validate_response
        packet = interpretation_packet(initialize(self.s), "library")
        response = {"packet_id": packet["packet_id"], "summary": "Availability is unknown."}
        self.assertEqual(validate_response(packet, response)["authority"], "unverified_commentary")
        for bad in [{**response, "action": "request_room_inspection"},
                    {**response, "packet_id": "wrong"},
                    {**response, "summary": ""}]:
            with self.assertRaises(ValueError):
                validate_response(packet, bad)

    def test_interpretation_rejects_non_demo_checkpoint(self):
        from interpretation import interpretation_packet
        self.s["id"] = "other"
        with self.assertRaises(ValueError):
            interpretation_packet(initialize(self.s), "library")

    def test_invalid_scenario_fields(self):
        for variant in [[], {**self.s, "typo": 1}, {**self.s, "id": ""},
                        {**self.s, "events": {}}, {**self.s, "constraints": [None]}]:
            with self.assertRaises(ValueError):
                initialize(variant)
        missing = copy.deepcopy(self.s)
        del missing["events"]
        with self.assertRaisesRegex(ValueError, "missing scenario fields"):
            initialize(missing)

    def test_validate_cli(self):
        import subprocess
        import sys
        root = Path(__file__).parent
        result = subprocess.run(
            [sys.executable, str(root / "runner.py"),
             str(root / "scenarios/demo.json"), "--validate"],
            capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def test_compare_completed_sessions(self):
        from comparison import compare
        a = initialize(self.s)
        b = submit_request(self.s, a, "library", {"action": "request_room_inspection"})
        for _ in range(2):
            a = advance(self.s, a)
            b = advance(self.s, b)
        result = compare(self.s, a, b)
        self.assertEqual(result["right_minus_left"]["requests"],
                         {"submitted": 1, "reviewed": 1, "pending": 0})
        self.assertEqual(result["right_minus_left"]["values"]["available_rooms"], 0)
        self.assertEqual(result["left"]["milestones"], {"passed": 2, "total": 2})

    def test_compare_rejects_incomplete_or_changed_scenario(self):
        from comparison import compare
        a = initialize(self.s)
        b = advance(self.s, advance(self.s, a))
        with self.assertRaisesRegex(ValueError, "completed sessions"):
            compare(self.s, a, b)
        revised = copy.deepcopy(self.s)
        revised["id"] = "changed"
        with self.assertRaisesRegex(ValueError, "scenario revision mismatch"):
            compare(revised, b, b)

    def test_library_request_dependent_outcome(self):
        from library_service import comparison
        result = comparison()
        self.assertEqual(result["additional_open_rooms"], 2)
        self.assertFalse(result["baseline"]["milestone"]["passed"])
        self.assertTrue(result["requested"]["milestone"]["passed"])
        self.assertEqual(result["requested"]["timeline"][0]["open_rooms"], [1])
        self.assertEqual(result["requested"]["timeline"][0]["pending_requests"], 1)

    def test_library_duplicate_and_invalid_requests(self):
        from library_service import run_library
        result = run_library([1, 1, 2])
        self.assertEqual(result["open_rooms"], [1, 2])
        self.assertEqual([r["result"] for r in result["ledger"]],
                         ["inspection_completed", "already_open", "inspection_completed"])
        self.assertEqual(run_library([2])["open_rooms"], [2])
        for bad in [[True], [3], "1"]:
            with self.assertRaises(ValueError):
                run_library(bad)

    def test_campaign_catalog(self):
        from campaign import load_campaign
        root = Path(__file__).parent / "campaigns/civic-recovery"
        data = load_campaign(root / "campaign.json")
        entries = [entry for group in data["groups"] for entry in group["scenarios"]]
        self.assertEqual(len(entries), 3)
        for entry in entries:
            scenario = json.loads((root / entry["file"]).read_text())
            state = initialize(scenario)
            while state["minute"] < scenario["end_minute"]:
                state = advance(scenario, state)
            verify_checkpoint(scenario, state)
            self.assertTrue(all(c["passed"] for c in state["checks"]))

    def test_campaign_invalid_references(self):
        from campaign import load_campaign
        import tempfile
        import shutil
        source = Path(__file__).parent / "campaigns/civic-recovery"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "campaign"
            shutil.copytree(source, root)
            path = root / "campaign.json"
            original = json.loads(path.read_text())
            for kind in ("duplicate", "missing_file", "missing_dependency", "cycle", "escape"):
                data = copy.deepcopy(original)
                first = data["groups"][0]["scenarios"][0]
                last = data["groups"][-1]["scenarios"][0]
                if kind == "duplicate":
                    data["groups"][0]["scenarios"].append(first)
                elif kind == "missing_file":
                    first["file"] = "absent.json"
                elif kind == "missing_dependency":
                    last["prerequisites"] = ["absent"]
                elif kind == "cycle":
                    first["prerequisites"] = [last["id"]]
                else:
                    first["file"] = "../outside.json"
                path.write_text(json.dumps(data))
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    load_campaign(path)

    def test_duplicate_event(self):
        self.s["events"].append(copy.deepcopy(self.s["events"][0]))
        with self.assertRaises(ValueError):
            initialize(self.s)

if __name__ == "__main__":
    unittest.main()
