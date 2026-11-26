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
            import base64
            png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB9sAAAAASUVORK5CYII=")
            (root / "map.png").write_bytes(png)
            git("add", "history.md", "map.png")
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
            entry["image_map"] = {"title": "Fixture map", "note": "Not georeferenced",
                "owner": "test", "revision": revision, "path": "map.png",
                "actors": ["relief"], "reviewed_for": "2000-01-01",
                "annotations": [{"id": "civilian-site", "label": "Illustrative public site", "pixel": [0, 0],
                    "actors": ["relief"], "known_from": "2000-01-01", "source": "Fixture",
                    "hex_id": "LOCAL:01"}]}
            entry["game_map"] = {"center": [0, 0], "zoom": 5, "note": "Synthetic geographic reference",
                "locations": [{"id": "local", "label": "Local <reference>", "coordinates": [0, 0],
                    "actors": ["relief"], "known_from": "2000-01-01", "source": "Illustrative fixture"}]}
            save(path, catalog)
            session = start(path, "external-relief", "relief", owners)
            from visualization import snapshot, render
            self.assertEqual(snapshot(session)["map"]["locations"][0]["id"], "local")
            self.assertNotIn("actors", snapshot(session)["map"]["locations"][0])
            self.assertIn("Load interactive map", render(session))
            self.assertEqual(snapshot(session)["image_map"]["width"], 1)
            self.assertEqual(snapshot(session)["image_map"]["annotations"][0]["hex_id"], "LOCAL:01")
            self.assertNotIn("actors", snapshot(session)["image_map"]["annotations"][0])
            self.assertNotIn("png_base64", snapshot(session)["image_map"])
            self.assertIn("data:image/png;base64,", render(session))
            self.assertIn("L.CRS.Simple", render(session))
            self.assertIn("age-spinner", render(session))
            self.assertIn("prefers-reduced-motion", render(session))
            self.assertIn('id="map-load-skeleton"', render(session))
            self.assertIn("Retry map", render(session))
            self.assertIn('aria-busy="false"', render(session))
            from image_map import resolve as resolve_image
            bad = {**entry, "image_map": {**entry["image_map"], "reviewed_for": "2000-01-02"}}
            with self.assertRaisesRegex(ValueError, "date-specific"):
                resolve_image(bad, session["header"]["compiled"], "2000-01-01", owners)
            from image_map import projection as image_projection
            self.assertIsNone(image_projection({"header": {**session["header"], "actor": "other"}}, True))
            self.assertNotIn("Local <reference>", render(session))
            self.assertNotIn("aid_packages", view(session)["observation"]["values"])
            opening = briefing(session)
            self.assertEqual(opening["kind"], "opening")
            self.assertEqual(opening["date"], "2000-01-01")
            self.assertNotIn("aid_packages", opening["reports"])
            self.assertNotIn("compiled", opening)
            from narrative import packet as narrative_packet, prompt as narrative_prompt, validate as validate_narrative
            narrative = narrative_packet(session)
            unchanged = digest(session)
            self.assertNotIn("aid_packages", narrative["briefing"]["reports"])
            self.assertIn("unknown", narrative_prompt(narrative))
            reply = {"packet_id": narrative["packet_id"], "summary": "Relief is underway."}
            self.assertEqual(validate_narrative(narrative, reply)["authority"], "unverified_model_commentary")
            with self.assertRaises(ValueError):
                validate_narrative(narrative, {**reply, "packet_id": "wrong"})
            self.assertEqual(digest(session), unchanged)
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
            # Interactive mode: choose scenario and actor, decline, confirm, save, resume.
            from interactive_play import run
            interactive = root / "interactive.json"
            output = []
            commands = iter(["1", "1", "deliver_aid", "n", "deliver_aid", "y", "next", "quit"])
            run(interactive, path, owners, ask=lambda _: next(commands), emit=output.append)
            resumed = verify(json.loads(interactive.read_text()))
            self.assertEqual(resumed["state"]["turn"], 1)
            self.assertEqual(len(resumed["state"]["requests"]), 1)
            commands = iter(["deliver_aid", "y", "next", "next"])
            run(interactive, ask=lambda _: next(commands), emit=output.append)
            final = verify(json.loads(interactive.read_text()))
            self.assertEqual(final["state"]["values"]["households_assisted"], 15)
            self.assertTrue(view(final)["complete"])
            self.assertTrue(any("Scenario complete" in line for line in output))
            # Reviewed hypothetical presets change resources and reporting, not canon.
            from private_play import available_presets
            entry["presets"] = {"scarce": {"label": "Scarce resources / delayed reports",
                "reason": "Illustrative stress case", "base_spec_digest": digest(spec),
                "resources": {"aid_packages": 1},
                "report_delays": {"relief": {"households_assisted": 60}}}}
            save(path, catalog)
            self.assertEqual([p["id"] for p in available_presets(path, "external-relief", owners)],
                             ["standard", "scarce"])
            variant = start(path, "external-relief", "relief", owners, "scarce")
            self.assertEqual(briefing(variant)["reports"]["households_assisted"]["status"], "unknown")
            self.assertEqual(briefing(variant)["preset"]["id"], "scarce")
            variant = update(variant, "deliver_aid", 1)
            self.assertEqual(briefing(variant)["reports"]["households_assisted"]["value"], 0)
            variant = update(variant, "deliver_aid", 2)
            self.assertEqual(variant["state"]["values"]["households_assisted"], 10)
            self.assertEqual(briefing(variant)["reports"]["households_assisted"]["value"], 10)
            from visualization import snapshot, render
            before_visual = digest(variant)
            visual = snapshot(variant)
            self.assertEqual(len(visual["metrics"]), 1)
            metric = visual["metrics"][0]
            self.assertEqual(metric["id"], "households_assisted")
            self.assertEqual(metric["report"]["status"], "stale")
            self.assertEqual(metric["observed_history"][-1], {"minute": 120, "value": 10})
            self.assertNotIn("aid_packages", json.dumps(visual))
            html = render(variant)
            self.assertIn("<svg", html)
            self.assertNotIn("aid_packages", html)
            self.assertEqual(digest(variant), before_visual)
            self.assertEqual(variant["state"]["values"]["aid_packages"], 0)
            self.assertEqual(variant["header"]["compiled"]["evidence"], session["header"]["compiled"]["evidence"])
            self.assertEqual(spec["scenario"]["initial"]["aid_packages"], 2)
            with self.assertRaises(ValueError):
                start(path, "external-relief", "relief", owners, "missing")
            entry["presets"]["scarce"]["resources"] = {"households_assisted": 10}
            save(path, catalog)
            with self.assertRaises(ValueError):
                start(path, "external-relief", "relief", owners, "scarce")
            # Independent human consent within a single authoritative shared checkpoint.
            from private_play import switch_perspective
            agreement = copy.deepcopy(spec)
            a = agreement["scenario"]
            a.pop("community_assistance")
            a.pop("assistance_capacity")
            a["id"] = "external-agreement"
            a["initial"] = {"participating_councils": 0, "council_a_joined": 0, "council_b_joined": 0}
            a["actors"] = {
                "council_a": {"label": "Council A", "visible_keys": ["participating_councils", "council_a_joined"]},
                "council_b": {"label": "Council B", "visible_keys": ["participating_councils", "council_b_joined"]}}
            a["civic_agreement"] = True
            a["action_catalog"] = {
                "join_council_a": {"description": "Council A joins", "actors": ["council_a"]},
                "join_council_b": {"description": "Council B joins", "actors": ["council_b"]}}
            save(root / "agreement.json", agreement)
            catalog["groups"][0]["scenarios"].append({
                "id": a["id"], "title": "Agreement", "spec": "agreement.json",
                "status": "reviewed-illustrative", "briefing_context": [
                    {"id": "a-context", "summary": "Council A local context.", "evidence": "context",
                     "actors": ["council_a"], "known_from": "2000-01-01", "reviewed_for": "2000-01-01"},
                    {"id": "b-context", "summary": "Council B local context.", "evidence": "context",
                     "actors": ["council_b"], "known_from": "2000-01-01", "reviewed_for": "2000-01-01"}]})
            save(path, catalog)
            with self.assertRaises(ValueError):
                start(path, a["id"], "council_a", owners)
            shared = start(path, a["id"], "council_a", owners, shared=True)
            self.assertEqual(briefing(shared)["context"][0]["id"], "a-context")
            with self.assertRaises(ValueError):
                update(shared, "join_council_b")
            shared = update(shared, "join_council_a", 1)
            self.assertEqual(shared["state"]["values"]["participating_councils"], 1)
            shared = switch_perspective(shared, "council_b")
            self.assertEqual(briefing(shared)["context"][0]["id"], "b-context")
            self.assertNotIn("council_a_joined", briefing(shared)["reports"])
            self.assertEqual(briefing(shared)["own_requests"], [])
            save(root / "shared.json", shared)
            shared = verify(json.loads((root / "shared.json").read_text()))
            shared = update(shared, "join_council_b", 1)
            self.assertEqual(shared["state"]["values"]["participating_councils"], 2)
            self.assertEqual(len(shared["state"]["requests"]), 2)
            shared = switch_perspective(shared, "council_a")
            self.assertEqual(len(briefing(shared)["own_requests"]), 1)
            with self.assertRaises(ValueError):
                switch_perspective(session, "relief")
            # Explicit continuation of the same civilian catchment, not a new canonical event.
            follow = copy.deepcopy(spec)
            follow["scenario"]["id"] = "external-relief-follow-on"
            follow["effective_date"] = "2000-01-02"
            follow["evidence_refs"]["context"]["reviewed_for"] = "2000-01-02"
            save(root / "follow.json", follow)
            mapping = {"scenario": "external-relief",
                       "variables": {"households_assisted": "households_assisted", "aid_packages": "aid_packages"},
                       "reason": "Same illustrative catchment and inventory",
                       "source_spec_digest": digest(spec), "target_spec_digest": digest(follow)}
            follow_entry = {"id": "external-relief-follow-on", "title": "Follow-on relief",
                            "spec": "follow.json", "status": "reviewed-illustrative",
                            "carry_from": mapping}
            catalog["groups"][0]["scenarios"].append(follow_entry)
            save(path, catalog)
            first = start(path, "external-relief", "relief", owners)
            with self.assertRaisesRegex(ValueError, "completed"):
                start(path, follow_entry["id"], "relief", owners, previous=first)
            first = update(first, "deliver_aid", 3)
            before = digest(first)
            second = start(path, follow_entry["id"], "relief", owners, previous=first)
            self.assertEqual(second["state"]["values"], {"households_assisted": 10, "aid_packages": 1})
            self.assertTrue(briefing(second)["continued"])
            self.assertNotIn("aid_packages", briefing(second)["reports"])
            self.assertEqual(second["header"]["continuity"]["source_session_digest"], before)
            self.assertEqual(digest(first), before)
            save(root / "follow-session.json", second)
            second = verify(json.loads((root / "follow-session.json").read_text()))
            second = update(second, "deliver_aid", 3)
            self.assertEqual(second["state"]["values"], {"households_assisted": 15, "aid_packages": 0})
            self.assertEqual(follow["scenario"]["initial"]["aid_packages"], 2)
            with self.assertRaises(ValueError):
                start(path, "external-agreement", "council_a", owners, shared=True, previous=first)
            mapping["variables"] = {"aid_packages": "aid_packages"}
            save(path, catalog)
            with self.assertRaises(ValueError):
                start(path, follow_entry["id"], "relief", owners, previous=first)
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
