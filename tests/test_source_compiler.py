import base64
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from age_runtime.core.source_compiler import compile_scenario, compile_variation, stale_dependencies
from age_runtime.core.runner import initialize, advance, verify_checkpoint, submit_request, digest


class SourceCompilerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.record = {"value": 2, "effective_date": "2003-04-01", "classification": "canonical"}
        self.write_source()
        self.revision = self.git("rev-parse", "HEAD").strip()
        scenario = json.loads((Path(__file__).resolve().parents[1] /
            "campaigns/civic-recovery/service-restoration.json").read_text())
        del scenario["initial"]["restoration_credits"]
        self.ref = {"owner": "synthetic", "revision": self.revision, "path": "facts.json",
                    "entity": "municipality", "field": "credits",
                    "effective_date": "2003-04-01", "classification": "canonical"}
        self.spec = {"version": 1, "effective_date": "2003-04-01", "scenario": scenario,
                     "initial_refs": {"restoration_credits": self.ref}}
        self.owners = {"synthetic": self.root}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True)

    def write_source(self):
        (self.root / "facts.json").write_text(json.dumps(
            {"entities": {"municipality": {"fields": {"credits": self.record}}}}))
        self.git("add", "facts.json")
        self.git("commit", "-qm", "fixture revision")

    def test_compile_deterministic_and_playable(self):
        snapshot = compile_scenario(self.spec, self.owners)
        self.assertEqual(snapshot, compile_scenario(self.spec, self.owners))
        self.assertEqual(stale_dependencies(snapshot, self.owners), [])
        scenario = snapshot["scenario"]
        state = submit_request(scenario, initialize(scenario), "coordinator",
                               {"action": "restore_service_center"})
        state = advance(scenario, state)
        self.assertEqual(state["values"]["restoration_credits"], 1)
        verify_checkpoint(scenario, state)
        self.assertNotIn("restoration_credits", self.spec["scenario"]["initial"])

    def test_revision_pinning_and_staleness(self):
        snapshot = compile_scenario(self.spec, self.owners)
        self.record["value"] = 4
        self.write_source()
        self.assertEqual(stale_dependencies(snapshot, self.owners), ["restoration_credits"])
        self.assertEqual(compile_scenario(self.spec, self.owners), snapshot)
        self.ref["revision"] = self.git("rev-parse", "HEAD").strip()
        revised = compile_scenario(self.spec, self.owners)
        self.assertEqual(revised["scenario"]["initial"]["restoration_credits"], 4)
        self.assertEqual(snapshot["scenario"]["initial"]["restoration_credits"], 2)

    def test_invalid_references_and_conflicts(self):
        for key, value in (("owner", "unknown"), ("revision", "HEAD"),
                           ("path", "../facts.json"), ("entity", "missing"),
                           ("effective_date", "2044-04-01"), ("classification", "unresolved"),
                           ("field", "missing")):
            with self.subTest(key=key):
                bad = copy.deepcopy(self.spec)
                bad["initial_refs"]["restoration_credits"][key] = value
                with self.assertRaises(ValueError):
                    compile_scenario(bad, self.owners)
        bad = copy.deepcopy(self.spec)
        bad["scenario"]["initial"]["restoration_credits"] = 1
        with self.assertRaises(ValueError):
            compile_scenario(bad, self.owners)

    def test_source_metadata_and_duplicate_keys(self):
        self.record["effective_date"] = "2044-04-01"
        self.write_source()
        self.ref["revision"] = self.git("rev-parse", "HEAD").strip()
        with self.assertRaises(ValueError):
            compile_scenario(self.spec, self.owners)
        (self.root / "facts.json").write_text('{"entities": {}, "entities": {}}')
        self.git("add", "facts.json")
        self.git("commit", "-qm", "ambiguous fixture")
        self.ref["revision"] = self.git("rev-parse", "HEAD").strip()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            compile_scenario(self.spec, self.owners)

    def test_variation_preserves_base_and_replays(self):
        from age_runtime.core.observations import observe
        base = compile_scenario(self.spec, self.owners)
        variation = {"version": 1, "id": "limited-budget",
                     "base_digest": digest(self.spec),
                     "initial_overrides": {"restoration_credits": {
                         "value": 1, "reason": "Illustrative reduced budget"}},
                     "report_delays": {"coordinator": {"open_service_centers": 60}}}
        snapshot = compile_variation(self.spec, variation, self.owners)
        self.assertEqual(snapshot, compile_variation(self.spec, variation, self.owners))
        self.assertEqual(base, compile_scenario(self.spec, self.owners))
        self.assertEqual(snapshot["dependencies"], base["dependencies"])
        self.assertEqual(snapshot["initial_overrides"]["restoration_credits"]["original"], 2)
        self.assertEqual(snapshot["initial_overrides"]["restoration_credits"]["classification"], "hypothetical")
        self.assertEqual(snapshot["base_scenario_digest"], base["scenario_digest"])
        scenario = snapshot["scenario"]
        self.assertEqual(scenario["id"], "service-restoration--limited-budget")
        state = initialize(scenario)
        for _ in range(2):
            state = submit_request(scenario, state, "coordinator", {"action": "restore_service_center"})
        state = advance(scenario, state)
        self.assertEqual(observe(scenario, state, "coordinator")["values"]["open_service_centers"], 0)
        state = advance(scenario, state)
        self.assertEqual(state["values"]["open_service_centers"], 3)
        self.assertEqual(state["requests"][1]["fulfillment"], "insufficient_credits")
        verify_checkpoint(scenario, state)
        with self.assertRaises(ValueError):
            verify_checkpoint(base["scenario"], state)

    def test_variation_rejects_unapproved_changes(self):
        good = {"version": 1, "id": "test", "base_digest": digest(self.spec),
                "initial_overrides": {}, "report_delays": {}}
        for change in (
                {"base_digest": "wrong"}, {"id": "../bad"}, {"version": True},
                {"initial_overrides": {"open_service_centers": {"value": 9, "reason": "test"}}},
                {"initial_overrides": {"restoration_credits": {"value": -1, "reason": "test"}}},
                {"initial_overrides": {"restoration_credits": {"value": 1, "reason": ""}}},
                {"report_delays": {"unknown": {}}},
                {"report_delays": {"coordinator": {"hidden": 0}}},
                {"report_delays": {"coordinator": {"open_service_centers": True}}},
                {"events": []}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                compile_variation(self.spec, {**good, **change}, self.owners)

    def test_narrative_evidence_without_numeric_extraction(self):
        (self.root / "history.md").write_text("# History\n\n## Recovery\nCivic services resumed.\n")
        self.git("add", "history.md")
        self.git("commit", "-qm", "narrative fixture")
        spec = copy.deepcopy(self.spec)
        spec["scenario"]["initial"]["restoration_credits"] = 2
        spec["initial_refs"] = {}
        ref = {"owner": "synthetic", "revision": self.git("rev-parse", "HEAD").strip(),
               "path": "history.md", "heading": "Recovery", "reviewed_for": spec["effective_date"],
               "classification": "canonical"}
        spec["evidence_refs"] = {"context": ref}
        snapshot = compile_scenario(spec, self.owners)
        self.assertEqual(snapshot, compile_scenario(spec, self.owners))
        self.assertNotIn("Civic services resumed", json.dumps(snapshot))
        self.assertEqual(snapshot["dependencies"], {})
        self.assertEqual(len(snapshot["evidence"]["context"]["section_sha256"]), 64)
        self.assertEqual(stale_dependencies(snapshot, self.owners), [])
        verify_checkpoint(snapshot["scenario"], initialize(snapshot["scenario"]))
        (self.root / "history.md").write_text("# History\n## Recovery\nUpdated.\n## Recovery\nDuplicate.\n")
        self.git("add", "history.md")
        self.git("commit", "-qm", "ambiguous heading")
        self.assertEqual(stale_dependencies(snapshot, self.owners), ["evidence:context"])
        self.assertEqual(snapshot, compile_scenario(spec, self.owners))
        ref["revision"] = self.git("rev-parse", "HEAD").strip()
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            compile_scenario(spec, self.owners)
        ref["reviewed_for"] = "2044-01-01"
        with self.assertRaisesRegex(ValueError, "review date"):
            compile_scenario(spec, self.owners)

    def test_connector_export_equivalence_and_tamper(self):
        (self.root / "history.md").write_text("# History\n\n## Recovery\nServices resumed.\n")
        self.git("add", "history.md")
        self.git("commit", "-qm", "evidence fixture")
        revision = self.git("rev-parse", "HEAD").strip()
        self.spec["evidence_refs"] = {"context": {
            "owner": "synthetic", "revision": revision, "path": "history.md",
            "heading": "Recovery", "reviewed_for": self.spec["effective_date"],
            "classification": "canonical"}}
        records = []
        for rev, path in ((self.revision, "facts.json"), (revision, "history.md")):
            raw = subprocess.check_output(["git", "-C", str(self.root), "show", rev + ":" + path])
            records.append({"revision": rev, "path": path,
                            "blob_sha": self.git("rev-parse", rev + ":" + path).strip(),
                            "content_base64": base64.b64encode(raw).decode("ascii")})
        owners = {"synthetic": {"kind": "connector-export-v1", "files": records}}
        expected = compile_scenario(self.spec, self.owners)
        self.assertEqual(compile_scenario(self.spec, owners), expected)
        for mutation in ("content", "hash", "missing", "duplicate", "revision"):
            bad = copy.deepcopy(owners)
            files = bad["synthetic"]["files"]
            if mutation == "content":
                files[0]["content_base64"] = "YQ=="
            elif mutation == "hash":
                files[0]["blob_sha"] = "0" * 40
            elif mutation == "missing":
                files.pop()
            elif mutation == "duplicate":
                files.append(files[0].copy())
            elif mutation == "revision":
                files[0]["revision"] = "0" * 40
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compile_scenario(self.spec, bad)
        with self.assertRaisesRegex(ValueError, "no local HEAD"):
            stale_dependencies(expected, owners)


    def test_signed_historical_source_dates(self):
        self.record["effective_date"] = "-1524-01-01"
        self.write_source()
        self.ref["revision"] = self.git("rev-parse", "HEAD").strip()
        self.ref["effective_date"] = self.spec["effective_date"] = "-1524-01-01"
        snapshot = compile_scenario(self.spec, self.owners)
        self.assertEqual(snapshot, compile_scenario(self.spec, self.owners))
        self.assertEqual(snapshot["dependencies"]["restoration_credits"]["effective_date"],
                         "-1524-01-01")
        self.ref["effective_date"] = "-1523-01-01"
        with self.assertRaisesRegex(ValueError, "effective date differs"):
            compile_scenario(self.spec, self.owners)
