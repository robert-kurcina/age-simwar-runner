"""Candidate authoring uses existing validation without registration."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from age_runtime.core.scenario_authoring import review_candidate

ROOT = Path(__file__).resolve().parents[1] / "scenarios/sh44ser/conflagration"


class ScenarioAuthoringTests(unittest.TestCase):
    def candidate(self, group):
        catalog = json.loads((ROOT / "inventory.json").read_bytes())
        entry = next(g for g in catalog["groups"] if g["id"] == group)["scenarios"][0]
        return {"title": entry["title"], "spec": json.loads((ROOT / entry["spec"]).read_bytes()),
                "player_factions": entry["player_factions"],
                "assumptions": ["Illustrative scenario values, not verified historical quantities."]}

    def test_economic_and_institutional_candidates(self):
        for group in ("mainlander-ingress", "purge"):
            candidate = self.candidate(group)
            before = deepcopy(candidate)
            report = review_candidate(candidate)
            self.assertEqual(report["status"], "rehearsable-unreviewed")
            self.assertFalse(report["registered"])
            self.assertEqual(report["author_review"], "pending")
            self.assertEqual(candidate, before)
            self.assertEqual(len(report["preparation"]["results"][0]["checks"]["rehearsal"]["perspectives"]),
                             len(candidate["player_factions"]))

    def test_unsupported_or_incomplete_candidates(self):
        candidate = self.candidate("mainlander-ingress")
        candidate["spec"]["scenario"]["turn_minutes"] = 1
        self.assertEqual(review_candidate(candidate)["status"], "blocked")
        candidate = self.candidate("purge")
        candidate["assumptions"] = []
        with self.assertRaises(ValueError):
            review_candidate(candidate)
        candidate = self.candidate("purge")
        candidate["status"] = "reviewed-illustrative"
        with self.assertRaises(ValueError):
            review_candidate(candidate)

    def test_reference_cannot_be_invented(self):
        candidate = self.candidate("mainlander-ingress")
        candidate["spec"]["initial_refs"] = {"missing": {"owner": "example"}}
        self.assertEqual(review_candidate(candidate)["status"], "blocked")
