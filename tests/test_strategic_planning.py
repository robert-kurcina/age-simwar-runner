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


    def test_early_assistance_vs_refusal_full_rehearsal(self):
        from age_runtime.core.private_play import (
            decision_brief, model_packet, model_choice, pending_factions, update, verify,
        )

        def route(accept, level):
            session = start_rehearsal(ROOT, SID, "fiji", opportunity_latitude=level)
            exchange = planning_packet(session, "Improve reception and secure early funds for claims")
            index = next(i for i, o in enumerate(exchange["decision_brief"]["diplomatic_options"])
                         if o.get("term") == "shanter_support_fiji")
            response = {"packet_id": exchange["packet_id"], "steps": [
                {"kind": "diplomacy", "value": index},
                {"kind": "action", "value": "fiji_reception_improve_logistics"},
                {"kind": "action", "value": "fiji_claims_improve_legal_permission"}]}
            self.assertEqual(validate_plan(session, exchange, response)["status"], "advisory_only")
            session = record_decision(session, digest(session), "aid", "Seek early assistance",
                                      negotiation_command={"kind": "propose", "id": "early",
                                          "recipient": "shanter", "transfers": ["shanter_support_fiji"],
                                          "due_minute": 10080})
            session = record_decision(session, digest(session), "reception", "Invest",
                                      "fiji_reception_improve_logistics")

            def resolve(session, choices):
                for actor in pending_factions(session):
                    packet = model_packet(session, actor)
                    session = model_choice(session, actor, {"packet_id": packet["packet_id"],
                                                            "action": choices.get(actor)})
                return verify(update(session, turns=1))

            session = resolve(session, {"shanter": {"kind": "accept" if accept else "reject",
                                                    "id": "early"},
                                        "vanuatu": "vanuatu_water_improve_logistics"})
            self.assertEqual(session["state"]["values"]["fiji_credits"], int(accept))
            with self.assertRaises(ValueError):
                validate_plan(session, exchange, response)
            if accept:
                fresh = planning_packet(session, "Use received funds for claims")
                self.assertEqual(validate_plan(session, fresh, {"packet_id": fresh["packet_id"],
                    "steps": [{"kind": "action", "value": "fiji_claims_improve_legal_permission"}]})
                    ["steps"][0]["option"]["assessment"]["currently_feasible"], True)
                session = record_decision(session, digest(session), "claims", "Invest received funds",
                                          "fiji_claims_improve_legal_permission")
            session = resolve(session, {"shanter": "shanter_reception_improve_logistics"})
            brief = decision_brief(session)
            self.assertEqual(brief["objective_outcomes"]["claims"]["status"],
                             "open" if accept else "objective_failure")
            self.assertFalse(brief["complete"])
            while not decision_brief(session)["complete"]:
                session = resolve(session, {})
            values = session["state"]["values"]
            self.assertEqual(values["fiji_reception_progress"], 3)
            self.assertEqual(values["fiji_claims_progress"], 3 if accept else 0)
            final = decision_brief(session)
            self.assertEqual(final["objective_outcomes"]["claims"]["status"],
                             "achieved" if accept else "objective_failure")
            self.assertFalse(final["recovery_assessment"]["alternatives"])
            return session["state"]

        for accept in (True, False):
            baseline = route(accept, "balanced")
            for level in ("permissive", "strict"):
                self.assertEqual(route(accept, level), baseline)
