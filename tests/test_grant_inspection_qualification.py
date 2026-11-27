"""Scripted independent decision exchanges, not an LLM competence benchmark."""
import copy
import json
from pathlib import Path
import unittest

from age_runtime.core.runner import (
    initialize, digest, verify_checkpoint, advance, communicate, assess_proposition,
    establish_context, record_diplomacy, commit_decision, faction_packet,
    accept_faction_choice, schedule_development,
)
from age_runtime.core.observations import observe
from age_runtime.core.institutional_memory import recall, reminder_index


class GrantInspectionQualification(unittest.TestCase):
    def scenario(self):
        return json.loads((Path(__file__).resolve().parents[1] /
                           "scenarios/grant-inspection-rehearsal.json").read_text())

    def choose(self, s, state, actor, action=None):
        packet = faction_packet(s, state, actor)
        return accept_faction_choice(s, state, actor, packet,
                                     {"packet_id": packet["packet_id"], "action": action})

    def decide(self, s, state, rid, intent, command):
        return commit_decision(s, state, "central", digest(state), rid, intent,
                               negotiation_command=command)

    def finish(self, s, state, chosen=()):
        for actor in s["model_factions"]:
            if actor not in chosen:
                state = self.choose(s, state, actor)
        state = advance(s, state)
        verify_checkpoint(s, state)
        return state

    def opening(self, s):
        state = initialize(s)
        hidden = faction_packet(s, state, "west")
        state = establish_context(s, state, digest(state), {"details": [{
            "id": "inc:office", "kind": "facility_detail", "label": "Service office",
            "description": "A reception room adjoining the records office.",
            "audience": ["central", "foundation"], "basis": "Reviewed synthetic setting."}]})
        state = communicate(s, state, "central", digest(state), {
            "id": "initial_report", "recipients": ["foundation"],
            "claim": "The inspection is already complete.", "proposition": "inspection",
            "asserts": True, "speaker_intent": "deceive"})
        state = assess_proposition(s, state, "foundation", digest(state), {
            "proposition": "inspection", "stance": "disbelieves",
            "basis": ["initial_report", "report:0"]})
        state = communicate(s, state, "central", digest(state), {
            "id": "correction", "recipients": ["foundation"], "corrects": "initial_report",
            "claim": "No completed inspection is documented.", "proposition": "inspection",
            "asserts": False})
        state = record_diplomacy(s, state, "foundation", digest(state), {
            "kind": "intention", "id": "verify_first", "counterpart": "central",
            "topic": "inspection", "text": "Seek independent access before considering a grant.",
            "status": "active", "revises": None})
        self.assertEqual(faction_packet(s, state, "west"), hidden)
        obs = observe(s, state, "foundation")
        self.assertEqual(obs["propositions"]["inspection"]["latest_stance"], "disbelieves")
        self.assertNotIn("speaker_intent", obs["communications"][0])
        self.assertNotIn("foundation", observe(s, state, "central")["diplomatic_history"].get("foundation", {}).get("private_intentions", {}))
        self.assertEqual(state["values"], s["initial"])
        state = self.decide(s, state, "offer", "Permit a supervised visit.", {
            "kind": "propose", "id": "supervised_offer", "recipient": "foundation",
            "permission": "supervised", "due_minute": 40320})
        state = self.choose(s, state, "foundation", {
            "kind": "counter", "id": "independent_offer", "recipient": "central",
            "permission": "independent", "due_minute": 40320, "parent": "supervised_offer"})
        self.assertEqual(state["negotiations"]["supervised_offer"]["status"], "countered")
        return state

    def run_route(self, s, opening, route):
        state = self.decide(s, opening, "response", "Choose reviewed inspection terms.", {
            "kind": "reject" if route == "refused" else "accept", "id": "independent_offer"})
        command = {"template": "inspection", "due_minute": 10080,
                   "permission_id": "independent_offer", "rationale": "Authorized inspection opportunity."}
        if route == "refused":
            before = digest(state)
            with self.assertRaises(ValueError):
                schedule_development(s, state, digest(state), command)
            self.assertEqual(digest(state), before)
        else:
            state = schedule_development(s, state, digest(state), command)
            if route == "revoked":
                state = self.decide(s, state, "revoke", "Withdraw permission.", {
                    "kind": "revoke", "id": "independent_offer"})
        state = self.finish(s, state, ("foundation",))
        expected = int(route == "cooperative")
        self.assertEqual(state["values"]["inspection_completed"], expected)
        self.assertEqual(state["values"]["foundation_reserve"], 2)
        self.assertEqual(observe(s, state, "central")["values"]["inspection_completed"], 0)
        obs = observe(s, state, "foundation")
        self.assertEqual(obs["values"]["inspection_completed"], expected)
        self.assertEqual(len(obs["developments"]), expected)
        state = assess_proposition(s, state, "foundation", digest(state), {
            "proposition": "inspection", "stance": "believes" if expected else "disbelieves",
            "basis": ["report:10080"]})
        # A funding decision is separate from permission or inspection.
        # Scripted choices deliberately differ across otherwise identical branches.
        if route == "cooperative":
            state = self.choose(s, state, "foundation", {
                "kind": "propose", "id": "grant", "recipient": "east",
                "transfers": ["grant_east"], "due_minute": 20160})
            state = self.choose(s, state, "east", {"kind": "accept", "id": "grant"})
            self.assertEqual(state["negotiations"]["grant"]["status"], "committed")
            self.assertEqual(state["values"]["east_credits"], 0)
            state = self.finish(s, state, ("foundation", "east"))
            self.assertEqual(state["negotiations"]["grant"]["status"], "fulfilled")
            self.assertEqual(state["values"]["east_credits"], 1)
        elif route == "revoked":
            state = self.choose(s, state, "foundation", "grant_west")
            state = self.finish(s, state, ("foundation",))
            self.assertEqual(state["values"]["west_credits"], 1)
        else:
            state = self.finish(s, state)
        self.assertEqual(observe(s, state, "central")["values"]["inspection_completed"], expected)
        self.assertNotIn("inspection", observe(s, state, "west")["propositions"])
        self.assertNotIn("inspection_completed", observe(s, state, "west")["values"])
        self.assertEqual(len(recall(observe(s, state, "central"))["developments"]), expected)
        if expected:
            self.assertIn("inspection", reminder_index(observe(s, state, "central"))["recent_development_ids"])
            state = self.choose(s, state, "east", "east_invest")
            state = self.finish(s, state, ("east",))
        elif route == "revoked":
            state = self.choose(s, state, "west", "west_invest")
            state = self.finish(s, state, ("west",))
        else:
            state = self.finish(s, state)
        state = self.finish(s, state)
        self.assertEqual(state["minute"], s["end_minute"])
        self.assertEqual(state["values"]["foundation_reserve"], 2 if route == "refused" else 1)
        return state

    def test_divergent_complete_episodes(self):
        s = self.scenario()
        opening = self.opening(s)
        frozen = digest(opening)
        results = {r: self.run_route(s, opening, r) for r in ("cooperative", "revoked", "refused")}
        self.assertEqual(digest(opening), frozen)
        self.assertEqual(results["cooperative"]["values"]["east_progress"], 2)
        self.assertEqual(results["cooperative"]["values"]["west_progress"], 0)
        self.assertEqual(results["revoked"]["values"]["west_progress"], 2)
        self.assertEqual(results["revoked"]["values"]["east_progress"], 0)
        self.assertEqual(results["refused"]["values"]["east_progress"], 0)
        self.assertEqual(results["refused"]["values"]["west_progress"], 0)
        self.assertEqual(results["revoked"]["generated_events"]["inspection"]["status"], "prerequisite_unmet")
        self.assertEqual(results["refused"]["generated_events"], {})
        self.assertEqual(len({digest(v) for v in results.values()}), 3)
        for route, state in results.items():
            self.assertEqual(digest(state), digest(self.run_route(s, opening, route)))
        tampered = copy.deepcopy(results["cooperative"])
        tampered["values"]["foundation_reserve"] += 1
        with self.assertRaises(ValueError):
            verify_checkpoint(s, tampered)
