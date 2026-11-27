"""Selective identities preserve earned information and replay."""
import unittest
import copy

from age_runtime.mythos import mythos, player_recap


class IncidentalPeopleTests(unittest.TestCase):
    def introduce(self, state):
        return mythos.establish_step(state, {"incidental_person": {
            "kind": "introduce", "id": "person:harbor_worker",
            "description": "A harbor worker in a weathered coat.",
            "basis": "An ordinary local encounter."}})

    def test_identity_promotion_and_replay(self):
        state = self.introduce(mythos.initial("boothbay", 42))
        original = copy.deepcopy(state)
        person = mythos.view(state)["incidental_people"][0]
        self.assertEqual(person["tier"], "incidental")
        self.assertIsNone(person["name"])
        self.assertNotIn("basis", person)
        self.assertNotIn("history", person)
        with self.assertRaises(ValueError):
            self.introduce(state)
        self.assertEqual(state, original)
        state = mythos.step(state, "observe")
        state = mythos.establish_step(state, {"incidental_person": {
            "kind": "recognize", "id": "person:harbor_worker",
            "basis": "The same distinctive coat and face."}})
        state = mythos.establish_step(state, {"incidental_person": {
            "kind": "promote", "id": "person:harbor_worker",
            "name": "Thomas Reed", "role": "Harbor worker",
            "basis": "He introduces himself."}})
        public = mythos.view(state)
        person = public["incidental_people"][0]
        self.assertEqual(person["tier"], "supporting")
        self.assertEqual(person["name"], "Thomas Reed")
        self.assertEqual(person["encounters"], 2)
        self.assertEqual(person["first_seen"], original["time"])
        self.assertNotIn("person:harbor_worker", state["npcs"])
        self.assertEqual(state["dxd"], mythos.step(original, "observe")["dxd"])
        self.assertEqual(player_recap.recall(public, "Thomas Reed")["total"], 1)
        self.assertEqual(player_recap.recap(public)["social_continuity"]["incidental_people"], [person])
        mythos.verify(state)

    def test_locality_and_identity_constraints(self):
        state = self.introduce(mythos.initial("boothbay", 42))
        for request in (
            {"kind": "recognize", "id": "person:harbor_worker", "basis": "Again."},
            {"kind": "promote", "id": "person:harbor_worker", "name": "Eleanor",
             "role": "Worker", "basis": "Introduces herself."},
            {"kind": "promote", "id": "person:harbor_worker", "name": "Thomas",
             "role": "Worker", "basis": "Introduction.", "skills": {"Investigate": 9}},
        ):
            with self.assertRaises(ValueError):
                mythos.establish_step(state, {"incidental_person": request})
        state = mythos.step(state, "move:Creek Inlet South")
        with self.assertRaises(ValueError):
            mythos.establish_step(state, {"incidental_person": {
                "kind": "recognize", "id": "person:harbor_worker", "basis": "A coincidence."}})
        mythos.verify(state)

    def test_no_automatic_residents(self):
        state = mythos.initial("boothbay", 42)
        self.assertEqual(state["incidental_people"], {})
        after = mythos.step(state, "observe")
        self.assertEqual(after["incidental_people"], {})
        self.assertEqual(mythos.gm_context(after, compact=True)["referee"]["incidental_people"], [])


    def test_cross_node_recognition_requires_elapsed_public_route(self):
        state = self.introduce(mythos.initial("boothbay", 42))
        request = {"incidental_person": {"kind": "recognize",
                    "id": "person:harbor_worker", "basis": "The same worker."}}
        impossible = copy.deepcopy(state)
        impossible["location"] = "Harbor Diner"
        impossible["time"] = "1927-10-13T08:04:59"
        with self.assertRaises(ValueError):
            mythos.establish_step(impossible, request)
        state = mythos.step(state, "move:Harbor Diner")
        state = mythos.establish_step(state, request)
        person = mythos.view(state)["incidental_people"][0]
        self.assertEqual(person["id"], "person:harbor_worker")
        self.assertEqual(person["location"], "Harbor Diner")
        self.assertEqual(person["encounters"], 2)
        mythos.verify(state)
