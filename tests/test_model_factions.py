import unittest
from age_runtime.core.runner import initialize, advance, submit_request, faction_packet, accept_faction_choice, verify_checkpoint
from age_runtime.core.observations import observe
from tests.test_economy import fixture

def scenario():
    s = fixture()
    s["events"] = []
    s["constraints"] = []
    s["initial"]["credits"] = 1
    s["actors"]["council"]["visible_keys"].append("credits")
    s["action_catalog"] = {"recruit": {"description": "Improve labor capacity", "actors": ["council"]}}
    s["administrative_reviews_per_turn"] = 1
    s["capacity_actions"] = {"recruit": {"project": "repair", "capacity": "labor", "resource": "credits", "cost": 1}}
    s["model_factions"] = ["council"]
    return s

class ModelFactionTests(unittest.TestCase):
    def test_model_choice_and_abstention_replay(self):
        s = scenario()
        a = initialize(s)
        packet = faction_packet(s, a, "council")
        with self.assertRaises(ValueError):
            advance(s, a)
        with self.assertRaises(ValueError):
            submit_request(s, a, "council", {"action": "recruit"})
        b = accept_faction_choice(s, a, "council", packet, {"packet_id": packet["packet_id"], "action": "recruit"})
        c = accept_faction_choice(s, a, "council", packet, {"packet_id": packet["packet_id"], "action": None})
        self.assertEqual(b["values"], a["values"])
        self.assertEqual(observe(s, b, "other")["own_requests"], [])
        self.assertEqual(advance(s, b)["values"]["stage"], 1)
        self.assertEqual(advance(s, c)["values"]["stage"], 0)
        for state in (advance(s, b), advance(s, c)):
            verify_checkpoint(s, state)
        with self.assertRaises(ValueError):
            accept_faction_choice(s, b, "council", packet, {"packet_id": packet["packet_id"], "action": None})
        d = advance(s, b)
        new = faction_packet(s, d, "council")
        with self.assertRaises(ValueError):
            accept_faction_choice(s, d, "council", new, {"packet_id": packet["packet_id"], "action": None})

    def test_reject_unsupported_response_and_tamper(self):
        s = scenario()
        a = initialize(s)
        p = faction_packet(s, a, "council")
        for response in ({"packet_id":p["packet_id"],"action":"invent"},
                         {"packet_id":p["packet_id"],"action":"recruit","cost":0}):
            with self.assertRaises(ValueError):
                accept_faction_choice(s, a, "council", p, response)
        b = accept_faction_choice(s, a, "council", p, {"packet_id":p["packet_id"],"action":None})
        b["requests"][0]["origin"] = "player"
        with self.assertRaises(ValueError):
            verify_checkpoint(s,b)


    def test_asymmetric_priorities_and_delayed_goal_reports(self):
        s = scenario()
        a = s["actors"]["council"]
        a["objectives"] = {
            "repair": {"description": "Restore service", "key": "stage",
                       "comparison": "at_least", "threshold": 2},
            "reserve": {"description": "Retain funds", "key": "credits",
                        "comparison": "at_least", "threshold": 1}}
        a["strategy"] = {"motivation": "Prioritize service continuity",
                         "priorities": ["repair", "reserve"]}
        other = s["actors"]["other"]
        other["visible_keys"] = ["stage"]
        other["report_delay_minutes"] = {"stage": 10080}
        other["objectives"] = {"wait": {"description": "Delay commitment",
                              "key": "stage", "comparison": "at_most", "threshold": 0}}
        other["strategy"] = {"motivation": "Protect institutional autonomy",
                             "priorities": ["wait"]}
        state = initialize(s)
        packet = faction_packet(s, state, "council")
        own = packet["observation"]["faction_strategy"]
        self.assertEqual([g["id"] for g in own["goals"]], ["repair", "reserve"])
        self.assertNotIn("Protect institutional autonomy", str(packet))
        visible = observe(s, state, "other")["faction_strategy"]
        self.assertIsNone(visible["goals"][0]["observed_result"])
        self.assertNotIn("Prioritize service continuity", str(visible))
        chosen = accept_faction_choice(s, state, "council", packet,
                   {"packet_id": packet["packet_id"], "action": "recruit"})
        after = advance(s, chosen)
        next_packet = faction_packet(s, after, "council")
        self.assertFalse(next_packet["observation"]["faction_strategy"]["goals"][1]["observed_result"]["met"])
        self.assertTrue(observe(s, after, "other")["faction_strategy"]["goals"][0]["observed_result"]["met"])
        verify_checkpoint(s, after)
        for priorities in ([], ["repair"], ["reserve", "reserve"], ["repair", "unknown"]):
            a["strategy"]["priorities"] = priorities
            with self.assertRaises(ValueError):
                initialize(s)
        a["strategy"]["priorities"] = ["repair", "reserve"]
        a["visible_keys"].remove("credits")
        with self.assertRaises(ValueError):
            initialize(s)


    def test_cross_faction_transfer_changes_opportunity_and_replays(self):
        from copy import deepcopy
        s = scenario()
        s["administrative_reviews_per_turn"] = 2
        s["initial"].update(other_credits=0, other_labor=2, other_stage=0,
                            other_delay=0, other_complications=0)
        s["actors"]["other"]["visible_keys"] = ["other_credits", "other_labor",
                                               "other_stage", "other_delay", "other_complications"]
        s["economy_projects"].append({"id": "other_repair", "participant": "other",
            "need": 3, "axes": [{"axis": "labor", "key": "other_labor"}],
            "stages": 2, "progress": "other_stage", "delay": "other_delay",
            "complications": "other_complications"})
        s["action_catalog"].update(other_recruit={"description": "Improve own labor", "actors": ["other"]},
                                   share={"description": "Transfer one credit to other", "actors": ["council"]})
        s["capacity_actions"]["other_recruit"] = {"project": "other_repair",
            "capacity": "other_labor", "resource": "other_credits", "cost": 1}
        s["resource_transfers"] = {"share": {"source": "credits", "destination": "other_credits", "amount": 1}}
        opening = initialize(s)
        packet = faction_packet(s, opening, "council")
        self.assertTrue(packet["observation"]["strategic_support"]["transfer_options"]["share"]["currently_feasible"])
        self.assertEqual(observe(s, opening, "other")["strategic_support"]["transfer_options"], {})
        with self.assertRaises(ValueError):
            submit_request(s, opening, "other", {"action": "share"})
        def play(action):
            state = accept_faction_choice(s, opening, "council", packet,
                        {"packet_id": packet["packet_id"], "action": action})
            return advance(s, state)
        shared, retained = play("share"), play("recruit")
        self.assertEqual((shared["values"]["credits"], shared["values"]["other_credits"]), (0, 1))
        self.assertEqual((retained["values"]["stage"], shared["values"]["stage"]), (1, 0))
        self.assertTrue(observe(s, shared, "other")["strategic_support"]["capacity_options"]["other_recruit"]["currently_feasible"])
        self.assertFalse(observe(s, retained, "other")["strategic_support"]["capacity_options"]["other_recruit"]["currently_feasible"])
        def finish(state):
            p = faction_packet(s, state, "council")
            state = accept_faction_choice(s, state, "council", p, {"packet_id": p["packet_id"], "action": "share"})
            state = submit_request(s, state, "other", {"action": "other_recruit"})
            return advance(s, state)
        end = finish(shared)
        self.assertEqual(end["values"]["other_stage"], 1)
        self.assertEqual(end["values"]["credits"], 0)
        self.assertEqual(end["requests"][-2]["fulfillment"], "insufficient_resources")
        self.assertEqual(end, finish(play("share")))
        verify_checkpoint(s, end)
        for key, value in (("amount", 0), ("amount", True), ("destination", "labor"),
                           ("destination", "credits"), ("source", "other_credits")):
            invalid = deepcopy(s)
            invalid["resource_transfers"]["share"][key] = value
            with self.assertRaises(ValueError):
                initialize(invalid)
        invalid = deepcopy(s)
        invalid["action_catalog"]["share"]["actors"] = ["other"]
        with self.assertRaises(ValueError):
            initialize(invalid)


    def test_mutual_agreement_settlement_and_default(self):
        from copy import deepcopy
        s = scenario()
        s["administrative_reviews_per_turn"] = 2
        s["initial"].update(other_credits=0, other_labor=2, other_stage=0,
                            other_delay=0, other_complications=0)
        s["actors"]["other"]["visible_keys"] = ["other_credits", "other_labor",
                                               "other_stage", "other_delay", "other_complications"]
        s["economy_projects"].append({"id": "other_repair", "participant": "other",
            "need": 3, "axes": [{"axis": "labor", "key": "other_labor"}],
            "stages": 2, "progress": "other_stage", "delay": "other_delay",
            "complications": "other_complications"})
        s["action_catalog"].update(other_recruit={"description": "Improve own labor", "actors": ["other"]},
                                   share={"description": "Transfer one credit to other", "actors": ["council"]})
        s["capacity_actions"]["other_recruit"] = {"project": "other_repair",
            "capacity": "other_labor", "resource": "other_credits", "cost": 1}
        s["resource_transfers"] = {"share": {"source": "credits", "destination": "other_credits", "amount": 1}}
        s["initial"]["other_credits"] = 1
        s["action_catalog"].update(return_credit={"description": "Return one credit", "actors": ["other"]},
                                   sign_a={"description": "Consent to exchange", "actors": ["council"]},
                                   sign_b={"description": "Consent to exchange", "actors": ["other"]})
        s["resource_transfers"]["return_credit"] = {"source": "other_credits", "destination": "credits", "amount": 1}
        s["agreements"] = {"exchange": {"description": "Reciprocal credit commitment",
            "consent": {"council": "sign_a", "other": "sign_b"},
            "transfers": ["share", "return_credit"], "due_minute": 2 * s["turn_minutes"]}}
        def step(state, model, human=None):
            packet = faction_packet(s, state, "council")
            state = accept_faction_choice(s, state, "council", packet,
                        {"packet_id": packet["packet_id"], "action": model})
            if human:
                state = submit_request(s, state, "other", {"action": human})
            return advance(s, state)
        opening = initialize(s)
        both = step(opening, "sign_a", "sign_b")
        self.assertEqual(observe(s, both, "other")["strategic_support"]["agreements"]["exchange"]["status"], "committed")
        self.assertEqual(both["values"]["credits"], 1)
        fulfilled = step(both, None)
        self.assertEqual(fulfilled["agreement_results"][0]["status"], "fulfilled")
        defaulted = step(both, "recruit")
        self.assertEqual(defaulted["agreement_results"][0]["status"], "defaulted")
        self.assertEqual(defaulted["values"]["other_credits"], 1)
        self.assertEqual(defaulted["values"]["credits"], 0)
        declined = step(step(opening, "sign_a"), None)
        self.assertEqual(declined["agreement_results"][0]["status"], "not_agreed")
        for state in (fulfilled, defaulted, declined):
            verify_checkpoint(s, state)
        self.assertEqual(defaulted, step(step(opening, "sign_a", "sign_b"), "recruit"))
        invalid = deepcopy(s)
        invalid["agreements"]["exchange"]["consent"]["other"] = "sign_a"
        with self.assertRaises(ValueError):
            initialize(invalid)
        invalid = deepcopy(s)
        invalid["agreements"]["exchange"]["due_minute"] = 1
        with self.assertRaises(ValueError):
            initialize(invalid)
