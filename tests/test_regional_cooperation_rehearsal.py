import copy
import json
import unittest
from pathlib import Path

from age_runtime.core.observations import observe
from age_runtime.core.runner import (
    initialize, advance, verify_checkpoint, digest, commit_decision,
    faction_packet, accept_faction_choice,
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


if __name__ == "__main__":
    unittest.main()
