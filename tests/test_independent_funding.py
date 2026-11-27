import copy
import json
from pathlib import Path
import unittest

from age_runtime.core.runner import (
    initialize, advance, verify_checkpoint, faction_packet, accept_faction_choice,
    submit_request, validate,
)
from age_runtime.core.private_play import supported
from age_runtime.core.negotiation import options
from age_runtime.core.private_continuity import continuity_keys


class IndependentFundingTest(unittest.TestCase):
    def scenario(self):
        return json.loads((Path(__file__).resolve().parents[1] /
                           "scenarios/independent-funding-rehearsal.json").read_text())

    def test_funding_routes_and_reserve_tradeoff(self):
        s = self.scenario()
        supported(s)
        for recipient in ("east", "west"):
            state = initialize(s)
            self.assertIn("grant_" + recipient, options(s, state, "foundation")[recipient])
            with self.assertRaises(ValueError):
                submit_request(s, state, "central", {"action": "grant_" + recipient})
            for turn in range(4):
                for actor in s["model_factions"]:
                    packet = faction_packet(s, state, actor)
                    action = ("grant_" + recipient if actor == "foundation" and turn == 0
                              else recipient + "_invest" if actor == recipient and turn == 1
                              else None)
                    state = accept_faction_choice(s, state, actor, packet,
                                                  {"packet_id": packet["packet_id"], "action": action})
                state = advance(s, state)
                verify_checkpoint(s, state)
            self.assertEqual(state["values"][recipient + "_progress"], 3)
            other = "west" if recipient == "east" else "east"
            self.assertEqual(state["values"][other + "_progress"], 0)
            self.assertEqual(state["values"]["foundation_reserve"], 1)
            self.assertEqual(sum(state["values"][k] for k in
                                 ("foundation_reserve", "central_credits", "east_credits", "west_credits")), 4)

    def test_invalid_funding_ownership(self):
        s = self.scenario()
        self.assertEqual(continuity_keys(s, s), set(s["initial"]))
        for mutation in ("duplicate", "unknown", "wrong_donor", "event", "hidden", "negative"):
            t = copy.deepcopy(s)
            if mutation == "duplicate":
                t["funding_reserves"]["central_credits"] = "foundation"
            elif mutation == "unknown":
                t["funding_reserves"]["foundation_reserve"] = "unknown"
            elif mutation == "wrong_donor":
                t["action_catalog"]["grant_east"]["actors"] = ["central"]
            elif mutation == "event":
                t["events"] = [{"id": "unreviewed", "minute": 1,
                                "key": "foundation_reserve", "delta": 1}]
            elif mutation == "hidden":
                t["actors"]["foundation"]["visible_keys"].remove("foundation_reserve")
            else:
                t["initial"]["foundation_reserve"] = -1
            with self.assertRaises(ValueError):
                validate(t)
        t = copy.deepcopy(s)
        t["capacity_actions"]["east_invest"]["cost"] = 2
        with self.assertRaises(ValueError):
            continuity_keys(s, t)
