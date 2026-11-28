"""Campaign discovery exposes verified opening choices, not referee state."""
import json
import tempfile
import unittest
from pathlib import Path

from age_runtime.core.campaign_discovery import discover

ROOT = Path(__file__).resolve().parents[1] / "scenarios/sh44ser/conflagration/inventory.json"


class CampaignDiscoveryTests(unittest.TestCase):
    def test_conflagration_menu(self):
        original = ROOT.read_bytes()
        menu = discover(ROOT)
        self.assertEqual(menu["groups"][0]["id"], "hexaday")
        self.assertFalse(menu["groups"][0]["episodes"])
        episodes = [e for g in menu["groups"] for e in g["episodes"]]
        self.assertEqual(len(episodes), 7)
        self.assertEqual(sum(len(e["perspectives"]) for e in episodes), 25)
        self.assertEqual(sum(e["turns"] for e in episodes), 31)
        self.assertEqual([e["effective_date"] for e in episodes],
                         sorted(e["effective_date"] for e in episodes))
        for episode in episodes:
            self.assertEqual(episode["play_mode"], "rehearse")
            self.assertEqual(episode["availability"], "available")
            self.assertEqual(episode["catalog_status"], "draft-unreviewed")
            self.assertEqual(set(episode), {"id", "title", "catalog_status", "play_mode",
                "availability", "perspectives", "effective_date", "turn_minutes", "turns",
                "opportunity_latitude", "shared_required"})
            self.assertTrue(all(set(p) == {"id", "label"} for p in episode["perspectives"]))
        self.assertEqual(ROOT.read_bytes(), original)

    def test_missing_spec_and_reviewed_source_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            catalog = json.loads(ROOT.read_bytes())
            entry = next(e for g in catalog["groups"] for e in g["scenarios"])
            missing = dict(entry, spec="missing.json")
            reviewed = dict(entry, id="reviewed", status="reviewed-illustrative")
            catalog["groups"] = [{"id": "test", "title": "Test", "status": "supported-pilot",
                                  "scenarios": [missing, reviewed]}]
            path.write_text(json.dumps(catalog), encoding="utf-8")
            episodes = discover(path)["groups"][0]["episodes"]
            self.assertEqual(episodes[0]["availability"], "blocked")
            self.assertEqual(episodes[1]["availability"], "requires-authorized-sources")
            self.assertTrue(all(e["play_mode"] is None and not e["perspectives"]
                                for e in episodes))


    def test_bundled_catalog_includes_both_draft_campaigns(self):
        from age_runtime.core.campaign_discovery import bundled_catalog
        campaigns = bundled_catalog()
        self.assertEqual(len(campaigns), 3)
        self.assertEqual(sum(len(c["episodes"]) for c in campaigns), 9)
        self.assertEqual(sum(len(e["perspectives"]) for c in campaigns for e in c["episodes"]), 31)
        self.assertTrue(all(c["qualification"] == "unreviewed-rehearsal" for c in campaigns))
        self.assertEqual(campaigns[1]["id"], "near-melanesia-2044")
        self.assertEqual(campaigns[2]["framework"], "great-war")
        self.assertEqual(campaigns[2]["episodes"][0]["duration"]["clock"], "event-driven-Time!")
        self.assertNotIn("inventory", campaigns[2])
        self.assertEqual(campaigns, bundled_catalog())
