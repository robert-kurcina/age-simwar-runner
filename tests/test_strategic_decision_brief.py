"""Decision brief projection: actor-local, detached and nonmechanical."""
import unittest

from age_runtime.core.decision_support import decision_brief
from age_runtime.core.observations import observe
from age_runtime.core.runner import initialize, digest, communicate
from tests.test_conflagration_drafts import load, decide, finish


class StrategicDecisionBriefTest(unittest.TestCase):
    def test_budget_conflict_and_read_only_projection(self):
        s = load("mainlander-ingress")["scenario"]
        state = initialize(s)
        before = digest(state)
        observation = observe(s, state, "fiji")
        original = digest(observation)
        brief = decision_brief(observation)
        warning = next(w for w in brief["shared_budget_warnings"]
                       if w["resource"] == "fiji_credits")
        self.assertEqual(warning["reported_balance"], 1)
        self.assertEqual({a["id"] for a in warning["alternatives"]},
                         {"fiji_reception_improve_logistics", "fiji_claims_improve_legal_permission"})
        self.assertEqual(brief["decision_pacing"]["count"], 0)
        self.assertEqual(brief["remaining_turns"], 4)
        brief["goals"].clear()
        brief["options"].clear()
        self.assertEqual(digest(observation), original)
        self.assertEqual(digest(state), before)

    def test_scope_and_contextual_history(self):
        s = load("mainlander-ingress")["scenario"]
        state = initialize(s)
        state = communicate(s, state, "fiji", digest(state), {
            "id": "private_status", "recipients": ["vanuatu"],
            "claim": "Claims procedures are not complete.",
            "proposition": "claims_ready", "asserts": False})
        state = decide(s, state, "fiji", "allocate_reception",
                       action="fiji_reception_improve_logistics")
        before = digest(state)
        player = decision_brief(observe(s, state, "fiji"))
        outsider = decision_brief(observe(s, state, "shanter"))
        self.assertEqual(player["recent_claims"][0]["id"], "private_status")
        self.assertEqual(player["recent_decisions"][0]["decision_id"], "allocate_reception")
        self.assertEqual(player["decision_pacing"]["count"], 1)
        self.assertEqual(outsider["recent_claims"], [])
        self.assertEqual(outsider["recent_decisions"], [])
        self.assertNotIn("aggregate_review_completed", outsider["uncertain_reports"])
        self.assertEqual(digest(state), before)

    def test_institutional_consent_and_terminal_options(self):
        s = load("purge")["scenario"]
        state = initialize(s)
        opening = decision_brief(observe(s, state, "fiji"))
        consent = next(o for o in opening["options"] if o["id"] == "fiji_safeguards")
        self.assertEqual(consent["kind"], "consent")
        self.assertEqual(consent["agreement"], "safeguards")
        self.assertTrue(opening["deadlines"])
        while state["minute"] < s["end_minute"]:
            state = finish(s, state)
        terminal = decision_brief(observe(s, state, "fiji"))
        self.assertEqual(terminal["options"], [])
        self.assertEqual(terminal["remaining_turns"], 0)
        self.assertEqual(terminal["decision_pacing"]["count"], 0)

    def test_faction_brief_preserves_packet_binding_and_scope(self):
        from unittest.mock import patch
        from age_runtime.core.private_play import model_decision_brief
        from age_runtime.core.runner import faction_packet, accept_faction_choice
        s = load("mainlander-ingress")["scenario"]
        state = initialize(s)
        state = communicate(s, state, "fiji", digest(state), {
            "id": "restricted_status", "recipients": ["vanuatu"],
            "claim": "Claims procedures remain incomplete.",
            "proposition": "claims_ready", "asserts": False})
        before = digest(state)
        for actor in ("shanter", "vanuatu"):
            packet = faction_packet(s, state, actor)
            with patch("age_runtime.core.private_play.model_packet", return_value=packet) as routed:
                exchange = model_decision_brief({}, actor)
                routed.assert_called_once_with({}, actor)
            self.assertEqual(exchange["packet"], packet)
            brief = exchange["decision_brief"]
            self.assertEqual(brief["actor"], actor)
            self.assertIsNone(brief["decision_pacing"])
            # The delayed communication is not yet visible to Vanuatu either.
            self.assertFalse(brief["recent_claims"])
            response = {"packet_id": exchange["packet"]["packet_id"], "action": None}
            candidate = accept_faction_choice(s, state, actor, packet, response)
            self.assertEqual(candidate["minute"], state["minute"])
            self.assertEqual(digest(state), before)
