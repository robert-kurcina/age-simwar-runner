"""Opportunity policy is session-bound and mechanically neutral."""
import unittest
from copy import deepcopy
from pathlib import Path

from age_runtime.core import opportunity_latitude as latitude
from age_runtime.core.draft_rehearsal import start_rehearsal
from age_runtime.core.private_play import verify, briefing, decision_brief
from age_runtime.core.runner import digest

ROOT = Path(__file__).resolve().parents[1] / "scenarios/sh44ser/conflagration/inventory.json"
SID = "mainlander-ingress-regional-draft"


class OpportunityLatitudeTest(unittest.TestCase):
    def test_levels_and_state_neutrality(self):
        base = start_rehearsal(ROOT, SID, "fiji")
        for level in latitude.LEVELS:
            session = start_rehearsal(ROOT, SID, "fiji", opportunity_latitude=level)
            self.assertEqual(session["state"], base["state"])
            self.assertEqual(session["header"]["compiled"], base["header"]["compiled"])
            self.assertEqual(briefing(session)["opportunity_policy"]["level"], level)
            self.assertEqual(decision_brief(session)["opportunity_policy"]["level"], level)
        self.assertEqual(base["header"]["opportunity_latitude"], "balanced")
        with self.assertRaises(ValueError):
            start_rehearsal(ROOT, SID, "fiji", opportunity_latitude="unlimited")

    def test_legacy_and_header_integrity(self):
        session = start_rehearsal(ROOT, SID, "fiji")
        legacy = deepcopy(session)
        del legacy["header"]["opportunity_latitude"]
        legacy["header_digest"] = digest(legacy["header"])
        self.assertEqual(briefing(legacy)["opportunity_policy"]["level"], "balanced")
        session["header"]["opportunity_latitude"] = "strict"
        with self.assertRaises(ValueError):
            verify(session)
        session["header"]["opportunity_latitude"] = "invalid"
        session["header_digest"] = digest(session["header"])
        with self.assertRaises(ValueError):
            verify(session)

    def test_closed_window_is_not_global_failure(self):
        projects = [{"id": "claims", "complete": False,
                     "horizon": {"possible_at_maximum_rate": False}},
                    {"id": "reception", "complete": True,
                     "horizon": {"possible_at_maximum_rate": False}}]
        for level in latitude.LEVELS:
            result = latitude.assess_projects(projects, level)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["category"], "opportunity_closure")
            self.assertFalse(result[0]["terminal_failure_established"])
            self.assertEqual(result[0]["scope"], "current-modeled-approach")
            self.assertEqual(latitude.assess_projects(projects, level, True)[0]["recovery_guidance"],
                             "Session ended; assess achieved outcomes only.")
        self.assertEqual(latitude.select("strict"), "strict")
        self.assertEqual(latitude.select("strict", "permissive"), "permissive")
