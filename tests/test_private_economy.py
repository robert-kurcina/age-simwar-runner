import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from age_runtime.core.private_play import start, update, briefing, perspectives, model_packet, model_choice, verify, pending_factions, resolve_turn, record_decision
from age_runtime.core.runner import digest
from tests.test_model_factions import scenario

class PrivateEconomyTests(unittest.TestCase):
    def test_private_project_choices_and_visibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(["git", "-C", tmp, *args], stderr=subprocess.DEVNULL).decode().strip()
            git("init")
            git("config", "user.email", "fixture@example.invalid")
            git("config", "user.name", "Fixture")
            (root / "history.md").write_text("# Recovery\nIllustrative recovery.\n")
            git("add", "history.md")
            git("commit", "-m", "Fixture")
            s = scenario()
            s["id"] = "private-recovery"
            s["administrative_reviews_per_turn"] = 2
            # The council is model-controlled; the other actor is the player.
            s["actors"]["other"]["visible_keys"] = ["stage"]
            spec = {"version": 1, "effective_date": "2000-01-01", "scenario": s,
                    "initial_refs": {}, "evidence_refs": {"history": {
                        "owner": "fixture", "revision": git("rev-parse", "HEAD"),
                        "path": "history.md", "heading": "Recovery",
                        "reviewed_for": "2000-01-01", "classification": "canonical"}}}
            (root / "spec.json").write_text(json.dumps(spec))
            entry = {"id": s["id"], "title": "Recovery", "spec": "spec.json",
                     "status": "reviewed-illustrative"}
            catalog = {"version": 1, "id": "fixture", "groups": [
                {"id": "recovery", "status": "supported-pilot", "scenarios": [entry]}]}
            path = root / "inventory.json"
            path.write_text(json.dumps(catalog))
            owners = {"fixture": tmp}
            self.assertEqual([p["id"] for p in perspectives(path, s["id"], owners)], ["other"])
            with self.assertRaises(ValueError):
                start(path, s["id"], "council", owners)
            a = start(path, s["id"], "other", owners)
            self.assertEqual(briefing(a)["projects"], [])
            support = briefing(a)["strategic_support"]
            self.assertEqual(support["capacity_options"], {})
            self.assertEqual(support["project_assessments"], [])
            self.assertEqual(pending_factions(a), ["council"])
            with self.assertRaises(ValueError):
                update(a, turns=1)
            packet = model_packet(a, "council")
            self.assertEqual(packet["observation"]["projects"][0]["need"], 3)
            support = packet["observation"]["strategic_support"]
            self.assertEqual(support["project_assessments"][0]["bottleneck"]["shortfall"], 1)
            self.assertEqual(support["capacity_options"]["recruit"]["cost"], 1)
            self.assertEqual(support["capacity_options"]["recruit"]["if_fulfilled"]["bottleneck"]["outcome"], "clear")
            response = {"packet_id": packet["packet_id"], "action": "recruit"}
            before = digest(a)
            for revision, responses in (("stale", {"council": response}),
                                        (before, {}),
                                        (before, {"council": {"packet_id": "bad", "action": "recruit"}})):
                with self.assertRaises(ValueError):
                    resolve_turn(a, revision, responses)
                self.assertEqual(digest(a), before)
            resolved = resolve_turn(a, before, {"council": response})
            b = model_choice(a, "council", response)
            self.assertEqual(pending_factions(b), [])
            self.assertEqual(resolve_turn(b, digest(b), {}), resolved)
            c = model_choice(a, "council", {"packet_id": packet["packet_id"], "action": None})
            b, c = update(b, turns=1), update(c, turns=1)
            self.assertEqual(b, resolved)
            self.assertEqual(briefing(b)["reports"]["stage"]["value"], 1)
            self.assertEqual(briefing(b)["strategic_support"]["report_changes"]["stage"]["delta"], 1)
            self.assertNotIn("credits", briefing(b)["strategic_support"]["report_changes"])
            self.assertEqual(briefing(b)["strategic_support"]["latest_project_results"], [])
            after = model_packet(b, "council")["observation"]["strategic_support"]
            self.assertFalse(after["capacity_options"]["recruit"]["currently_feasible"])
            self.assertEqual(after["capacity_options"]["recruit"]["reason"], "insufficient_resources")
            self.assertEqual(briefing(c)["reports"]["stage"]["value"], 0)
            self.assertNotIn("credits", briefing(b)["reports"])
            self.assertEqual(briefing(b)["own_requests"], [])
            verify(b)
            verify(c)

            paced = start(path, s["id"], "other", owners, game_length="Short")
            self.assertEqual(briefing(paced)["decision_pacing"]["target"], 6)
            self.assertEqual(briefing(paced)["decision_pacing"]["count"], 0)
            self.assertNotIn("decision_pacing", model_packet(paced, "council")["observation"])
            revision = digest(paced)
            chosen = record_decision(paced, revision, "hold-1", "Preserve current commitments")
            self.assertEqual(briefing(chosen)["decision_pacing"]["count"], 1)
            self.assertEqual(chosen["state"]["minute"], 0)
            for rev, key in ((revision, "hold-2"), (digest(chosen), "hold-1")):
                with self.assertRaises(ValueError):
                    record_decision(chosen, rev, key, "Hold")
            packet = model_packet(chosen, "council")
            completed = resolve_turn(chosen, digest(chosen), {
                "council": {"packet_id": packet["packet_id"], "action": "recruit"}})
            self.assertEqual(briefing(completed)["decision_pacing"]["count"], 1)
            self.assertEqual(completed["state"]["turn"], 1)
            verify(completed)
            with self.assertRaises(ValueError):
                start(path, s["id"], "other", owners, game_length="20")
