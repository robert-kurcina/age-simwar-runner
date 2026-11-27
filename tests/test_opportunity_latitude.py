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


    def test_objective_bounds_and_terminal_report_uncertainty(self):
        definitions = {
            "full": {"key": "progress", "threshold": 3, "comparison": "at_least", "description": "Full"},
            "partial": {"key": "progress", "threshold": 1, "comparison": "at_least", "description": "Partial"},
            "limit": {"key": "progress", "threshold": 0, "comparison": "at_most", "description": "Limit"},
            "reserve": {"key": "stock", "threshold": 1, "comparison": "at_least", "description": "Reserve"},
        }
        observed = {"full": {"actual": 1, "met": False}, "partial": {"actual": 1, "met": True},
                    "limit": {"actual": 1, "met": False}, "reserve": {"actual": 0, "met": False}}
        reports = {"progress": {"status": "current"}, "stock": {"status": "stale"}}
        projects = [{"progress": "progress", "stages": 3}]
        outcomes = latitude.objective_outcomes(definitions, observed, reports, projects, 30, 40, 10)
        self.assertEqual(outcomes["full"]["status"], "objective_failure")
        self.assertEqual(outcomes["full"]["modeled_range"], {"minimum": 1, "maximum": 2})
        self.assertEqual(outcomes["partial"]["status"], "currently_met")
        self.assertEqual(outcomes["limit"]["status"], "objective_failure")
        self.assertEqual(outcomes["reserve"]["status"], "unconfirmed")
        terminal = latitude.objective_outcomes(definitions, observed, reports, projects, 40, 40, 10)
        self.assertEqual(terminal["partial"]["status"], "achieved")
        self.assertEqual(terminal["full"]["status"], "objective_failure")
        self.assertEqual(terminal["reserve"]["status"], "unconfirmed")

    def test_actual_goal_failure_does_not_end_session(self):
        from age_runtime.core.private_play import pending_factions, model_packet, model_choice, update
        session = start_rehearsal(ROOT, SID, "fiji")
        for _ in range(2):
            for actor in pending_factions(session):
                packet = model_packet(session, actor)
                session = model_choice(session, actor, {"packet_id": packet["packet_id"], "action": None})
            session = update(session, turns=1)
        brief = decision_brief(session)
        self.assertEqual(brief["objective_outcomes"]["claims"]["status"], "objective_failure")
        self.assertEqual(brief["objective_outcomes"]["reserve"]["status"], "currently_met")
        self.assertFalse(brief["complete"])
        self.assertFalse(brief["recovery_assessment"]["terminal_failure_established"])
        self.assertTrue(brief["recovery_assessment"]["alternatives"])
        self.assertEqual(briefing(session)["objective_outcomes"], brief["objective_outcomes"])


    def test_institutional_deadline_and_dependent_objective(self):
        from age_runtime.core.private_play import pending_factions, model_packet, model_choice, update
        sid = "purge-institutional-draft"
        session = start_rehearsal(ROOT, sid, "fiji")
        opening = decision_brief(session)
        self.assertEqual(opening["objective_outcomes"]["claims"]["status"], "open")
        self.assertEqual(opening["objective_outcomes"]["safeguards"]["status"], "open")
        for actor in pending_factions(session):
            packet = model_packet(session, actor)
            session = model_choice(session, actor, {"packet_id": packet["packet_id"], "action": None})
        session = update(session, turns=1)
        before = digest(session)
        brief = decision_brief(session)
        for ident in ("claims", "safeguards"):
            self.assertEqual(brief["objective_outcomes"][ident]["status"], "objective_failure")
            self.assertEqual(brief["objective_outcomes"][ident]["modeled_range"], {"minimum": 0, "maximum": 0})
        self.assertFalse(brief["complete"])
        self.assertFalse(brief["recovery_assessment"]["terminal_failure_established"])
        self.assertEqual(digest(session), before)
        # A different signatory has a separate, still attainable relief objective.
        from age_runtime.core.observations import observe
        scenario = session["header"]["compiled"]["scenario"]
        other = observe(scenario, session["state"], "vanuatu")
        self.assertEqual(other["objective_outcomes"]["local_relief"]["status"], "open")
        self.assertNotIn("claims", other["objective_outcomes"])

    def test_institutional_bounds_require_current_evidence(self):
        agreements = {
            "first": {"outcome": "a", "due_minute": 10, "requires": []},
            "second": {"outcome": "b", "due_minute": 20, "requires": ["first"]},
            "third": {"outcome": "c", "due_minute": 30, "requires": ["second"]},
        }
        reports = {k: {"status": "current", "value": 0} for k in ("a", "b", "c")}
        self.assertEqual(latitude.institutional_bounds(agreements, reports, 0), {})
        fixed = latitude.institutional_bounds(agreements, reports, 10)
        self.assertEqual({k: v["value"] for k, v in fixed.items()}, {"a": 0, "b": 0, "c": 0})
        reports["a"]["status"] = "stale"
        self.assertEqual(latitude.institutional_bounds(agreements, reports, 10), {})
        reports["a"] = {"status": "current", "value": 1}
        fixed = latitude.institutional_bounds(agreements, reports, 10)
        self.assertEqual({k: v["value"] for k, v in fixed.items()}, {"a": 1})
