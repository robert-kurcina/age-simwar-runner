import copy
import json
import unittest
from pathlib import Path

from age_runtime.core.observations import observe
from age_runtime.core.runner import (
    initialize, advance, verify_checkpoint, digest, commit_decision,
    faction_packet, accept_faction_choice, negotiate,
)


class RegionalCooperationRehearsal(unittest.TestCase):
    def setUp(self):
        self.s = json.loads((Path(__file__).resolve().parents[1] /
                             "scenarios/regional-cooperation-rehearsal.json").read_text())

    def choose(self, state, actor, action):
        packet = faction_packet(self.s, state, actor)
        return accept_faction_choice(self.s, state, actor, packet,
                                     {"packet_id": packet["packet_id"], "action": action})

    def play(self, cooperate):
        state = initialize(self.s)
        timeline = []
        for turn in range(4):
            if turn == 0:
                action = "central_support_east" if cooperate else "central_invest"
                state = commit_decision(self.s, state, "central", digest(state),
                                        "opening", action, action)
            elif turn == 1 and cooperate:
                state = commit_decision(self.s, state, "central", digest(state),
                                        "local-recovery", "Invest locally", "central_invest")
            # Fixed alternative-dependent inputs, not a claimed live LLM trial.
            east_action = ("east_invest" if state["values"]["east_credits"] > 0
                           and state["values"]["east_capacity"] < 3 else None)
            west_action = "west_invest" if turn == 0 else None
            state = self.choose(state, "east", east_action)
            state = self.choose(state, "west", west_action)
            state = advance(self.s, state)
            verify_checkpoint(self.s, state)
            timeline.append(observe(self.s, state, "central"))
        return state, timeline

    def test_divergent_paths_and_replay(self):
        shared, timeline = self.play(True)
        local, other = self.play(False)
        self.assertEqual(shared["values"]["central_progress"], 3)
        self.assertEqual(local["values"]["central_progress"], 3)
        self.assertEqual(shared["values"]["east_progress"], 3)
        self.assertEqual(local["values"]["east_progress"], 0)
        self.assertEqual(shared["values"]["west_progress"], 3)
        self.assertEqual(local["values"]["west_progress"], 3)
        self.assertEqual(shared["values"]["central_credits"], 1)
        self.assertEqual(local["values"]["central_credits"], 2)
        self.assertNotEqual(timeline[0]["values"], other[0]["values"])
        self.assertNotIn("east_credits", timeline[-1]["values"])
        self.assertEqual(timeline[-1]["decision_pacing"]["count"], 2)
        self.assertEqual(other[-1]["decision_pacing"]["count"], 1)
        self.assertEqual(self.play(True)[0], shared)
        altered = copy.deepcopy(shared)
        altered["values"]["east_progress"] += 1
        with self.assertRaises(ValueError):
            verify_checkpoint(self.s, altered)


    def negotiated_path(self, response):
        state = initialize(self.s)
        due = self.s["turn_minutes"]
        proposal = {"kind": "propose", "id": "relief-offer", "recipient": "east",
                    "transfers": ["central_support_east"], "due_minute": due}
        state = negotiate(self.s, state, "central", digest(state), proposal)
        # Only the two participating councils receive the proposal.
        self.assertEqual(observe(self.s, state, "west")["negotiation"]["proposals"], [])
        self.assertEqual(state["values"], self.s["initial"])
        if response == "counter":
            command = {"kind": "counter", "id": "relief-counter", "parent": "relief-offer",
                       "recipient": "central", "transfers": ["central_support_east"],
                       "due_minute": due * 2}
            state = self.choose(state, "east", command)
            self.assertEqual(state["negotiations"]["relief-offer"]["status"], "countered")
            state = negotiate(self.s, state, "central", digest(state),
                              {"kind": "accept", "id": "relief-counter"})
            self.assertEqual(state["negotiations"]["relief-counter"]["status"], "committed")
        else:
            command = None if response == "ignore" else {"kind": response, "id": "relief-offer"}
            state = self.choose(state, "east", command)
        state = commit_decision(self.s, state, "central", digest(state),
                                "local-investment", "Restore local services", "central_invest")
        state = self.choose(state, "west", "west_invest")
        self.assertEqual(state["values"], self.s["initial"])
        for turn in range(4):
            if turn:
                # Respond only to this faction's observed resources, not hidden state.
                east = observe(self.s, state, "east")["values"]
                action = "east_invest" if east["east_credits"] and east["east_capacity"] < 3 else None
                state = self.choose(state, "east", action)
                state = self.choose(state, "west", None)
            state = advance(self.s, state)
            verify_checkpoint(self.s, state)
            if turn == 0:
                expected = {"accept": "fulfilled", "reject": "rejected",
                            "ignore": "expired", "counter": "countered"}
                self.assertEqual(state["negotiations"]["relief-offer"]["status"], expected[response])
        return state

    def test_negotiation_changes_recovery_timing_and_reserves(self):
        accepted = self.negotiated_path("accept")
        refused = self.negotiated_path("reject")
        expired = self.negotiated_path("ignore")
        countered = self.negotiated_path("counter")
        for state in (accepted, refused, expired, countered):
            self.assertEqual(state["values"]["central_progress"], 3)
            self.assertEqual(state["values"]["west_progress"], 3)
            self.assertEqual(observe(self.s, state, "central")["decision_pacing"]["count"], 1)
        self.assertEqual(accepted["values"]["east_progress"], 3)
        self.assertEqual(refused["values"]["east_progress"], 0)
        self.assertEqual(expired["values"]["east_progress"], 0)
        self.assertEqual(countered["values"]["east_progress"], 2)
        self.assertEqual(countered["negotiations"]["relief-counter"]["status"], "fulfilled")
        self.assertEqual(accepted["values"]["central_credits"], 1)
        self.assertEqual(countered["values"]["central_credits"], 1)
        self.assertEqual(refused["values"]["central_credits"], 2)
        self.assertEqual(expired["values"]["central_credits"], 2)
        self.assertEqual(self.negotiated_path("counter"), countered)
        altered = copy.deepcopy(countered)
        altered["negotiations"]["relief-counter"]["status"] = "rejected"
        with self.assertRaises(ValueError):
            verify_checkpoint(self.s, altered)

    def test_negotiation_cannot_bind_an_uninvolved_council(self):
        state = initialize(self.s)
        with self.assertRaises(ValueError):
            negotiate(self.s, state, "central", digest(state),
                      {"kind": "propose", "id": "invalid-offer", "recipient": "east",
                       "transfers": ["west_support_east"], "due_minute": self.s["turn_minutes"]})
        self.assertEqual(state, initialize(self.s))


if __name__ == "__main__":
    unittest.main()
