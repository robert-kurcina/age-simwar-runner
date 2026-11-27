"""Advisory multi-step planning must not execute or bypass existing orders."""
import unittest
from copy import deepcopy
from pathlib import Path

from age_runtime.core.draft_rehearsal import start_rehearsal
from age_runtime.core.player_requests import planning_packet, planning_prompt, validate_plan
from age_runtime.core.private_play import record_decision
from age_runtime.core.runner import digest

ROOT = Path(__file__).resolve().parents[1] / "scenarios/sh44ser/conflagration/inventory.json"
SID = "mainlander-ingress-regional-draft"


class StrategicPlanningTest(unittest.TestCase):
    def test_combined_proposal_is_advisory_and_policy_neutral(self):
        results = []
        for level in ("permissive", "balanced", "strict"):
            session = start_rehearsal(ROOT, SID, "fiji", opportunity_latitude=level)
            before = digest(session)
            exchange = planning_packet(session, "Seek assistance and improve both services")
            brief = exchange["decision_brief"]
            self.assertEqual(brief["opportunity_policy"]["level"], level)
            self.assertIn("never when", planning_prompt(exchange))
            self.assertTrue(brief["diplomatic_options"])
            response = {"packet_id": exchange["packet_id"], "steps": [
                {"kind": "diplomacy", "value": 0},
                {"kind": "action", "value": "fiji_reception_improve_logistics"},
                {"kind": "action", "value": "fiji_claims_improve_legal_permission"},
                {"kind": "unresolved", "value": "Explore alternative administrative arrangements."}]}
            plan = validate_plan(session, exchange, response)
            self.assertEqual(plan["status"], "advisory_only")
            self.assertEqual([x["status"] for x in plan["steps"]], [
                "requires_actual_terms_and_consent", "requires_fresh_confirmation",
                "requires_fresh_confirmation", "unverified_no_mechanical_effect"])
            self.assertEqual(digest(session), before)
            results.append(plan["steps"])
        self.assertEqual(results[0], results[2])

    def test_invalid_steps_and_stale_exchange(self):
        session = start_rehearsal(ROOT, SID, "fiji")
        exchange = planning_packet(session, "Explore recovery")
        for step in (
            {"kind": "action", "value": "invent_funds"},
            {"kind": "diplomacy", "value": True},
            {"kind": "diplomacy", "value": -1},
            {"kind": "unresolved", "value": " "},
            {"kind": "action", "value": "fiji_reception_improve_logistics", "effects": {}},
        ):
            with self.assertRaises(ValueError):
                validate_plan(session, exchange, {"packet_id": exchange["packet_id"], "steps": [step]})
        altered = deepcopy(exchange)
        altered["decision_brief"]["options"] = []
        with self.assertRaises(ValueError):
            validate_plan(session, altered, {"packet_id": exchange["packet_id"], "steps": []})
        changed = record_decision(session, digest(session), "reception", "Invest",
                                  "fiji_reception_improve_logistics")
        with self.assertRaises(ValueError):
            validate_plan(changed, exchange, {"packet_id": exchange["packet_id"], "steps": []})
