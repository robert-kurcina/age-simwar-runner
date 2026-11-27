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


    def test_recovery_assessment_actor_local_and_neutral(self):
        from age_runtime.core.private_play import pending_factions, model_packet, model_choice, update
        from age_runtime.core.private_play import record_decision
        session = start_rehearsal(ROOT, SID, "fiji")
        initial = digest(session)
        opening = decision_brief(session)["recovery_assessment"]
        self.assertTrue(any(x["kind"] == "diplomatic_option" for x in opening["alternatives"]))
        self.assertFalse(opening["closures"])
        self.assertEqual(digest(session), initial)
        session = record_decision(session, digest(session), "reception", "Prioritize reception",
                                  "fiji_reception_improve_logistics")
        for _ in range(2):
            for actor in pending_factions(session):
                packet = model_packet(session, actor)
                session = model_choice(session, actor, {"packet_id": packet["packet_id"], "action": None})
            session = update(session, turns=1)
        brief = decision_brief(session)
        before = digest(session)
        assessments = [latitude.recovery_assessment(brief, level) for level in latitude.LEVELS]
        for assessment in assessments:
            self.assertTrue(any(c["project"] == "fiji_claims" for c in assessment["closures"]))
            claim = next(a for a in assessment["alternatives"]
                         if a.get("project") == "fiji_claims")
            self.assertEqual(claim["scope"], "mitigation_only")
            self.assertEqual(claim["status"], "conditional")
            self.assertTrue(assessment["novel_proposals"]["player_proposals_allowed"])
            self.assertFalse(assessment["terminal_failure_established"])
        self.assertEqual(assessments[0]["alternatives"], assessments[2]["alternatives"])
        self.assertEqual(digest(session), before)
        ended = latitude.recovery_assessment(brief, "permissive", complete=True)
        self.assertFalse(ended["alternatives"])
        self.assertFalse(ended["novel_proposals"]["player_proposals_allowed"])
        self.assertFalse(ended["terminal_failure_established"])

    def test_no_known_recovery_is_not_terminal_failure(self):
        brief = {"projects": [], "options": [], "diplomatic_options": [], "remaining_turns": 1}
        result = latitude.recovery_assessment(brief, "strict")
        self.assertFalse(result["alternatives"])
        self.assertFalse(result["terminal_failure_established"])
        self.assertTrue(result["novel_proposals"]["player_proposals_allowed"])
