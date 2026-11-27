import copy
import json
from pathlib import Path
import unittest

from age_runtime.core.runner import (
    initialize, advance, submit_request, faction_packet, accept_faction_choice,
    verify_checkpoint, validate,
)
from age_runtime.core.observations import observe
from age_runtime.core.private_play import supported, eligible_perspectives


class InstitutionalConsentTest(unittest.TestCase):
    def scenario(self):
        return json.loads((Path(__file__).resolve().parents[1] /
                           "scenarios/institutional-consent-rehearsal.json").read_text())

    def decide(self, s, state, actor, action):
        packet = faction_packet(s, state, actor)
        return accept_faction_choice(s, state, actor, packet,
                                     {"packet_id": packet["packet_id"], "action": action})

    def test_consent_and_missing_prerequisite(self):
        s = self.scenario()
        supported(s)
        for consent in (True, False):
            state = initialize(s)
            with self.assertRaises(ValueError):
                submit_request(s, state, "council", {"action": "relief_protection"})
            state = submit_request(s, state, "council", {"action": "council_protection"})
            with self.assertRaises(ValueError):
                submit_request(s, state, "council", {"action": "council_protection"})
            state = self.decide(s, state, "mediators", "mediators_protection")
            state = self.decide(s, state, "relief", "relief_protection" if consent else None)
            state = advance(s, state)
            verify_checkpoint(s, state)
            self.assertEqual(state["values"]["protection_agreed"], int(consent))
            with self.assertRaises(ValueError):
                submit_request(s, state, "council", {"action": "council_protection"})
            self.assertNotIn("settlement", observe(s, state, "relief")["strategic_support"]["agreements"])
            state = submit_request(s, state, "council", {"action": "council_settlement"})
            state = self.decide(s, state, "mediators", "mediators_settlement")
            state = self.decide(s, state, "relief", None)
            state = advance(s, state)
            verify_checkpoint(s, state)
            self.assertEqual(state["values"]["settlement_agreed"], int(consent))
            self.assertEqual(state["agreement_results"][-1]["status"],
                             "fulfilled" if consent else "prerequisite_unmet")
            damaged = copy.deepcopy(state)
            damaged["values"]["settlement_agreed"] = 1 - int(consent)
            with self.assertRaises(ValueError):
                verify_checkpoint(s, damaged)

    def test_validation_and_selectable_roles(self):
        s = self.scenario()
        allowed = list(s["actors"])
        self.assertEqual(eligible_perspectives({"player_factions": allowed}, s), allowed)
        for human in allowed:
            t = copy.deepcopy(s)
            t["model_factions"] = [a for a in allowed if a != human]
            supported(t)
            initialize(t)
        for mutation in ("same_deadline", "duplicate_outcome", "wrong_authority", "hidden_outcome", "event"):
            t = copy.deepcopy(s)
            if mutation == "same_deadline":
                t["agreements"]["settlement"]["due_minute"] = 10080
            elif mutation == "duplicate_outcome":
                t["agreements"]["settlement"]["outcome"] = "protection_agreed"
            elif mutation == "wrong_authority":
                t["action_catalog"]["relief_protection"]["actors"] = ["council"]
            elif mutation == "hidden_outcome":
                t["actors"]["relief"]["visible_keys"] = []
            else:
                t["events"] = [{"id": "forced", "minute": 1, "key": "protection_agreed", "delta": 1}]
            with self.assertRaises(ValueError):
                validate(t)
