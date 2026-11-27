import copy
import json
from pathlib import Path
import unittest

from age_runtime.core.runner import initialize, communicate, digest, verify_checkpoint, commit_decision
from age_runtime.core.observations import observe
from age_runtime.core.institutional_memory import recall, reminder_index


class InstitutionalMemoryTest(unittest.TestCase):
    def test_actor_scoped_read_only_recall(self):
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/independent-funding-rehearsal.json").read_text())
        s["material_communications"] = True
        s["runtime_propositions"] = True
        state = initialize(s)
        human = next(a for a in s["actors"] if a not in s["model_factions"])
        sender, other = s["model_factions"][:2]
        state = communicate(s, state, sender, digest(state),
                            {"id": "earlier", "recipients": [human],
                             "claim": "A preliminary inspection remains necessary.",
                             "proposition": "inc:inspection", "asserts": True,
                             "introduce_proposition": {"id": "inc:inspection", "text": "Inspection is necessary."},
                             "speaker_intent": "sincere"})
        state = commit_decision(s, state, human, digest(state), "defer",
                                "Defer pending independent inspection.")
        before = digest(state)
        observation = observe(s, state, human)
        memory = recall(observation)
        self.assertEqual(memory["decisions"][-1]["decision_id"], "defer")
        self.assertEqual(memory["communications"][0]["id"], "earlier")
        self.assertNotIn("speaker_intent", memory["communications"][0])
        self.assertIn("inc:inspection", memory["propositions"])
        self.assertEqual(recall(observation, sender)["communications"][0]["id"], "earlier")
        self.assertEqual(recall(observation, other)["communications"], [])
        self.assertEqual(recall(observe(s, state, other))["communications"], [])
        self.assertIn("inc:inspection", reminder_index(observation)["unsettled_proposition_ids"])
        memory["communications"][0]["claim"] = "Altered."
        self.assertEqual(digest(state), before)
        verify_checkpoint(s, state)

    def test_deadlines_are_sorted_and_scoped(self):
        observation = {"actor": "a", "turn": 2, "minute": 20, "objectives": {},
                       "reports": {}, "available_requests": {},
                       "negotiation": {"proposals": [
                           {"id": "late", "proposer": "a", "recipient": "b",
                            "status": "committed", "due_minute": 40},
                           {"id": "closed", "proposer": "a", "recipient": "c",
                            "status": "rejected", "due_minute": 25}]},
                       "strategic_support": {"agreements": {
                           "early": {"status": "awaiting_consent", "due_minute": 30}}}}
        self.assertEqual([x["id"] for x in reminder_index(observation)["outstanding_deadlines"]],
                         ["early", "late"])
        self.assertEqual([x["id"] for x in recall(observation, "c")["proposals"]], ["closed"])
