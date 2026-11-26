import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from private_play import inventory, perspectives, start, update, view, verify
from runner import save


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
                     "status": "verified-illustrative-pilot"}
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
            session = start(path, "external-relief", "relief", owners)
            self.assertNotIn("aid_packages", view(session)["observation"]["values"])
            session = update(session, "deliver_aid", 1)
            save(root / "session.json", session)
            # Resume without the source files or inventory.
            path.unlink()
            (root / "spec.json").unlink()
            session = verify(json.loads((root / "session.json").read_text()))
            session = update(session, "deliver_aid", 2)
            self.assertTrue(view(session)["complete"])
            self.assertEqual(view(session)["observation"]["values"]["households_assisted"], 15)
            session["header"]["actor"] = "other"
            with self.assertRaises(ValueError):
                verify(session)
            entry["status"] = "provisional"
            save(path, catalog)
            with self.assertRaisesRegex(ValueError, "catalog-only"):
                start(path, "external-relief", "relief", owners)
