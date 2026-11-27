"""Preparation is a diagnostic, not a promotion or a gameplay gate."""
import json
import tempfile
import unittest
from pathlib import Path

from age_runtime.core.scenario_preparation import prepare

ROOT = Path(__file__).resolve().parents[1] / "scenarios/sh44ser/conflagration/inventory.json"


class ScenarioPreparationTests(unittest.TestCase):
    def test_actual_draft_catalog_without_sources(self):
        original = ROOT.read_bytes()
        report = prepare(ROOT)
        self.assertEqual(len(report["results"]), 7)
        self.assertIn("hexaday", report["catalog_only_groups"])
        self.assertIsNone(report["resource_discovery_error"])
        self.assertTrue(report["resources"])
        self.assertTrue(all(r["status"] == "not-checked" for r in report["resources"]))
        count = 0
        for result in report["results"]:
            self.assertEqual(result["catalog_status"], "draft-unreviewed")
            self.assertEqual(result["author_review"], "pending")
            self.assertEqual(result["checks"]["rehearsal"]["status"], "passed")
            self.assertEqual(result["checks"]["compilation"]["status"], "not-checked")
            count += len(result["checks"]["rehearsal"]["perspectives"])
        self.assertEqual(count, 25)
        self.assertEqual(ROOT.read_bytes(), original)

    def test_unavailable_sources_do_not_block_rehearsal(self):
        report = prepare(ROOT, {})
        self.assertTrue(all(r["status"] == "unavailable-or-invalid" for r in report["resources"]))
        for result in report["results"]:
            self.assertEqual(result["checks"]["rehearsal"]["status"], "passed")
            self.assertEqual(result["checks"]["compilation"]["status"], "blocked")
            self.assertEqual(result["author_review"], "pending")

    def test_bad_spec_does_not_hide_other_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            catalog = json.loads(ROOT.read_bytes())
            entries = [e for group in catalog["groups"] for e in group["scenarios"]]
            good = dict(entries[0], spec="good.json")
            bad = dict(entries[1], spec="missing.json")
            (path.parent / "good.json").write_bytes((ROOT.parent / entries[0]["spec"]).read_bytes())
            catalog["groups"] = [dict(catalog["groups"][0], scenarios=[bad, good])]
            path.write_text(json.dumps(catalog))
            report = prepare(path)
            self.assertIsNotNone(report["resource_discovery_error"])
            self.assertEqual(report["results"][0]["checks"]["specification"]["status"], "blocked")
            self.assertEqual(report["results"][1]["checks"]["rehearsal"]["status"], "passed")


    def test_roster_review_preserves_unresolved_context(self):
        report = prepare(ROOT)
        for result in report["results"]:
            review = result["roster_review"]
            self.assertFalse(review["unbound_profiles"])
            self.assertEqual(set(review["eligible_perspectives"]),
                             {a["id"] for a in review["actors"] if a["selectable"]})
            for actor in review["actors"]:
                self.assertEqual(actor["profile_status"], "literal-checked")
                self.assertTrue(actor["profile_present"])
                self.assertTrue(actor["objectives"])
                self.assertTrue(actor["hypothetical_properties"])
                self.assertTrue(actor["unresolved_properties"])

    def test_roster_distinguishes_candidate_from_bound_actor(self):
        from copy import deepcopy
        from age_runtime.core.scenario_preparation import roster_review
        catalog = json.loads(ROOT.read_bytes())
        group = next(g for g in catalog["groups"] if g["id"] == "reconstruction")
        entry = group["scenarios"][0]
        spec = json.loads((ROOT.parent / entry["spec"]).read_bytes())
        candidate = json.loads((ROOT.parent / "reconstruction/wpc-profile-draft.json").read_bytes())
        spec["faction_profiles"]["wpc"] = candidate
        before = deepcopy(spec)
        review = roster_review(spec, entry)
        self.assertEqual(review["unbound_profiles"], ["wpc"])
        self.assertNotIn("wpc", review["eligible_perspectives"])
        self.assertEqual(spec, before)
        actor = next(iter(spec["scenario"]["actors"]))
        spec["faction_profiles"][actor]["effective_date"] = "1900-01-01"
        review = roster_review(spec, entry)
        self.assertEqual(next(a for a in review["actors"] if a["id"] == actor)
                         ["profile_status"], "blocked")
