"""Contrasting scripted campaign outcomes; not independent LLM gameplay."""
import unittest
from age_runtime.core.runner import initialize, digest, verify_checkpoint
from tests.test_conflagration_drafts import load, choose, decide, finish


class ConflagrationOutcomes(unittest.TestCase):
    def run_orders(self, group, human, orders):
        s = load(group)["scenario"]
        s["model_factions"] = [a for a in s["actors"] if a != human]
        state = initialize(s)
        while state["minute"] < s["end_minute"]:
            turn = state["turn"]
            actions = orders.get(turn, {})
            if human in actions:
                state = decide(s, state, human, "decision-" + str(turn),
                               action=actions[human])
            state = finish(s, state, actions=actions)
        verify_checkpoint(s, state)
        return state

    def repeat(self, group, human, orders):
        first = self.run_orders(group, human, orders)
        self.assertEqual(digest(first), digest(self.run_orders(group, human, orders)))
        return first

    def test_disaster_response_relief_tradeoff(self):
        # One credit can fund either reception or clinic supply. A grant
        # arrives at the turn boundary, not before the recipient's order.
        for project, other in (("emergency_reception", "clinic_supply"),
                               ("clinic_supply", "emergency_reception")):
            with self.subTest(project=project):
                local = self.repeat("disaster-response", "fiji", {
                    0: {"fiji": "invest_" + project, "vanuatu": "invest_water_distribution"}})
                shared = self.repeat("disaster-response", "fiji", {
                    0: {"fiji": "invest_" + project, "shanter": "shanter_grant_fiji",
                        "vanuatu": "invest_water_distribution"},
                    1: {"fiji": "invest_" + other}})
                self.assertEqual(local["values"][project + "_progress"], 2)
                self.assertEqual(local["values"][other + "_progress"], 0)
                self.assertEqual(shared["values"][project + "_progress"], 2)
                self.assertEqual(shared["values"][other + "_progress"], 2)
                self.assertEqual(local["values"]["shanter_credits"], 1)
                self.assertEqual(shared["values"]["shanter_credits"], 0)

    def test_ingress_competing_services(self):
        for project, axis, other, other_axis in (
                ("reception", "logistics", "claims", "legal_permission"),
                ("claims", "legal_permission", "reception", "logistics")):
            with self.subTest(project=project):
                invest = "fiji_" + project + "_improve_" + axis
                alternate = "fiji_" + other + "_improve_" + other_axis
                alone = self.repeat("mainlander-ingress", "fiji", {0: {"fiji": invest}})
                shared = self.repeat("mainlander-ingress", "fiji", {
                    0: {"fiji": invest, "shanter": "shanter_support_fiji"},
                    1: {"fiji": alternate}})
                self.assertEqual(alone["values"]["fiji_" + project + "_progress"], 3)
                self.assertEqual(alone["values"]["fiji_" + other + "_progress"], 0)
                self.assertEqual(shared["values"]["fiji_" + other + "_progress"], 3)
                self.assertEqual(shared["values"]["aggregate_review_completed"], 0)

    def test_reconstruction_multiple_bottlenecks(self):
        # Port requires two separate investments. Housing can progress
        # without new funding. Local energy and regional grant compete.
        orders = {
            0: {"fiji": "fiji_port_improve_logistics",
                "shanter": "shanter_support_fiji",
                "vanuatu": "vanuatu_power_improve_energy"},
            1: {"fiji": "fiji_port_improve_materials",
                "shanter": "shanter_technical_improve_energy"}}
        shared = self.repeat("reconstruction", "fiji", orders)
        orders[0] = {k: v for k, v in orders[0].items() if k != "shanter"}
        orders[1] = {"shanter": "shanter_technical_improve_energy"}
        local = self.repeat("reconstruction", "fiji", orders)
        self.assertEqual(shared["values"]["fiji_port_progress"], 4)
        self.assertEqual(local["values"]["fiji_port_progress"], 0)
        for state in (shared, local):
            self.assertEqual(state["values"]["fiji_housing_progress"], 4)
            self.assertEqual(state["values"]["vanuatu_power_progress"], 4)
            self.assertEqual(state["values"]["shanter_technical_progress"], 4)
        self.assertEqual(shared["values"]["shanter_credits"], 0)
        self.assertEqual(local["values"]["shanter_credits"], 2)

    def institutional(self, group, human, sequence, withheld=None):
        s = load(group)["scenario"]
        orders = {}
        for turn, aid in enumerate(sequence):
            orders[turn] = {actor: action for actor, action in
                            s["agreements"][aid]["consent"].items()
                            if (aid, actor) != withheld}
        return self.repeat(group, human, orders)

    def test_purge_consent_and_independent_relief(self):
        seq = ["safeguards", "local_relief", "claims", "regional_referrals"]
        full = self.institutional("purge", "fiji", seq)
        split = self.institutional("purge", "fiji", seq, ("safeguards", "shanter"))
        self.assertTrue(all(v == 1 for v in full["values"].values()))
        self.assertEqual(split["values"], {"safeguards_agreed": 0, "claims_agreed": 0,
                         "local_relief_agreed": 1, "regional_referrals_agreed": 0})
        self.assertEqual({a["id"]: a["status"] for a in split["agreement_results"]},
                         {"safeguards": "not_agreed", "local_relief": "fulfilled",
                          "claims": "prerequisite_unmet", "regional_referrals": "prerequisite_unmet"})

    def test_agreement_distinct_religious_and_national_commitments(self):
        seq = ["regional_principles", "religious_witness", "national_coordination",
               "claims_consultation"]
        full = self.institutional("agreement", "shanter", seq)
        split = self.institutional("agreement", "shanter", seq,
                                   ("religious_witness", "arabian-religious-delegation"))
        self.assertTrue(all(v == 1 for v in full["values"].values()))
        self.assertEqual(split["values"], {"regional_principles_agreed": 1,
                         "national_coordination_agreed": 1, "religious_witness_agreed": 0,
                         "claims_consultation_agreed": 1})
        blocked = self.institutional("agreement", "shanter", seq,
                                     ("regional_principles", "vanuatu"))
        self.assertTrue(all(v == 0 for v in blocked["values"].values()))
