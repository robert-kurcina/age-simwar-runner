import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from private_play import inventory, perspectives, start, update, view, verify, briefing
from runner import save, digest
from player_requests import packet, prompt, validate_proposal, confirm


class PrivatePlayTest(unittest.TestCase):
    def test_start_resume_and_actor_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(["git", "-C", tmp, *args]).decode().strip()
            git("init")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            (root / "history.md").write_text("# Context\nSynthetic civilian relief.\n")
            git("add", "history.md")
            git("commit", "-m", "Evidence")
            revision = git("rev-parse", "HEAD")
            spec = {"version": 1, "effective_date": "2000-01-01", "initial_refs": {},
                    "evidence_refs": {"context": {"owner": "test", "revision": revision,
                    "path": "history.md", "heading": "Context", "reviewed_for": "2000-01-01",
                    "classification": "canonical"}},
                    "scenario": {"version": 1, "id": "external-relief", "turn_minutes": 60,
                    "end_minute": 180, "initial": {"households_assisted": 0, "aid_packages": 2},
                    "events": [], "constraints": [], "community_assistance": True,
                    "assistance_capacity": {"household_limit": 15, "households_per_package": 10},
                    "administrative_reviews_per_turn": 1,
                    "actors": {"relief": {"label": "Relief", "visible_keys": ["households_assisted"]}},
                    "action_catalog": {"deliver_aid": {"description": "Deliver relief", "actors": ["relief"]}}}}
            save(root / "spec.json", spec)
            entry = {"id": "external-relief", "title": "Relief", "spec": "spec.json",
                     "status": "verified-illustrative-pilot", "briefing_context": [
                         {"id": "relief-context", "summary": "Synthetic civilian relief is underway.",
                          "evidence": "context", "actors": ["relief"], "known_from": "2000-01-01",
                          "reviewed_for": "2000-01-01"}]}
            catalog = {"version": 1, "id": "external", "groups": [
                {"id": "recovery", "status": "supported-pilot", "scenarios": [entry]},
                {"id": "archive", "status": "catalog-only", "scenarios": []}]}
            path = root / "inventory.json"
            save(path, catalog)
            owners = {"test": tmp}
            self.assertEqual(len(inventory(path)["groups"]), 2)
            self.assertEqual(perspectives(path, "external-relief", owners), [{"id": "relief", "label": "Relief"}])
            with self.assertRaises(ValueError):
                start(path, "external-relief", "unknown", owners)
            entry["briefing_context"][0]["known_from"] = "2000-01-02"
            save(path, catalog)
            with self.assertRaisesRegex(ValueError, "future context"):
                start(path, "external-relief", "relief", owners)
            entry["briefing_context"][0]["known_from"] = "2000-01-01"
            save(path, catalog)
            session = start(path, "external-relief", "relief", owners)
            self.assertNotIn("aid_packages", view(session)["observation"]["values"])
            opening = briefing(session)
            self.assertEqual(opening["kind"], "opening")
            self.assertEqual(opening["date"], "2000-01-01")
            self.assertNotIn("aid_packages", opening["reports"])
            self.assertNotIn("compiled", opening)
            self.assertEqual(opening["context"][0]["id"], "relief-context")
            self.assertEqual(opening["context"][0]["classification"], "canonical")
            self.assertNotIn("path", opening["context"][0])
            exchange = packet(session, "Please deliver aid.")
            response = {"packet_id": exchange["packet_id"], "action": "deliver_aid"}
            original = digest(session)
            self.assertIn("available_requests", prompt(exchange))
            self.assertEqual(validate_proposal(session, exchange, response)["status"],
                             "requires_confirmation")
            self.assertEqual(digest(session), original)
            self.assertEqual(validate_proposal(session, exchange, {**response, "action": None})["status"],
                             "unresolved")
            with self.assertRaises(ValueError):
                validate_proposal(session, exchange, {**response, "action": "unsupported"})
            with self.assertRaises(ValueError):
                confirm(session, exchange, response, "wrong")
            session = confirm(session, exchange, response, "deliver_aid")
            self.assertEqual(session["state"]["values"]["households_assisted"], 0)
            with self.assertRaisesRegex(ValueError, "stale"):
                validate_proposal(session, exchange, response)
            session = update(session, turns=1)
            self.assertEqual(briefing(session)["kind"], "turn")
            self.assertEqual(briefing(session)["elapsed_minutes"], 60)
            save(root / "session.json", session)
            # A distinct restoration scenario uses the same compiler and session API.
            import copy
            restoration = copy.deepcopy(spec)
            s = restoration["scenario"]
            s.pop("community_assistance")
            s.pop("assistance_capacity")
            s["id"] = "external-restoration"
            s["initial"] = {"open_service_centers": 0, "restoration_credits": 2}
            s["actors"]["relief"]["visible_keys"] = ["open_service_centers"]
            s["service_restoration"] = True
            s["action_catalog"] = {"restore_service_center": {"description": "Restore service", "actors": ["relief"]}}
            save(root / "restoration.json", restoration)
            catalog["groups"][0]["scenarios"].append({"id": s["id"], "title": "Restoration",
                "spec": "restoration.json", "status": "reviewed-illustrative"})
            save(path, catalog)
            restored = start(path, s["id"], "relief", owners)
            for _ in range(3):
                restored = update(restored, "restore_service_center", 1)
            self.assertEqual(view(restored)["observation"]["values"]["open_service_centers"], 2)
            self.assertEqual(restored["state"]["values"]["restoration_credits"], 0)
            self.assertTrue(view(restored)["complete"])
            # Resume without the source files or inventory.
            path.unlink()
            (root / "spec.json").unlink()
            session = verify(json.loads((root / "session.json").read_text()))
            session = update(session, "deliver_aid", 2)
            self.assertTrue(view(session)["complete"])
            self.assertEqual(briefing(session)["context"], opening["context"])
            self.assertEqual(view(session)["observation"]["values"]["households_assisted"], 15)
            session["header"]["actor"] = "other"
            with self.assertRaises(ValueError):
                verify(session)
            entry["status"] = "provisional"
            save(path, catalog)
            with self.assertRaisesRegex(ValueError, "catalog-only"):
                start(path, "external-relief", "relief", owners)
