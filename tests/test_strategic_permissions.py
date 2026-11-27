import copy
import json
from pathlib import Path
import unittest

from age_runtime.core.runner import (initialize, negotiate, digest, verify_checkpoint,
                                     faction_packet, accept_faction_choice, advance)
from age_runtime.core.negotiation import active_permission
from age_runtime.core.observations import observe
from age_runtime.core.institutional_memory import recall


class StrategicPermissionTests(unittest.TestCase):
    def scenario(self):
        s = json.loads((Path(__file__).resolve().parents[1] /
                        "scenarios/institutional-consent-rehearsal.json").read_text())
        s.update(dynamic_negotiation=True, material_communications=True,
                 diplomatic_history=True)
        s["permission_terms"] = {
            "visit": {"issuer": "council", "grantee": "mediators",
                      "description": "Visit the public records office.",
                      "max_due_minute": 20160},
            "supervised_visit": {"issuer": "council", "grantee": "mediators",
                                 "description": "Visit with an administrative escort.",
                                 "max_due_minute": 10080}}
        return s

    def model(self, s, state, actor, action=None):
        packet = faction_packet(s, state, actor)
        return accept_faction_choice(s, state, actor, packet,
                                     {"packet_id": packet["packet_id"], "action": action})

    def offer(self, pid="offer", **extra):
        return dict(kind="propose", id=pid, recipient="mediators",
                    permission="visit", due_minute=20160, **extra)

    def test_permission_accept_revoke_and_no_fulfillment(self):
        s = self.scenario()
        state = initialize(s)
        baseline = copy.deepcopy(state)
        hidden = faction_packet(s, state, "relief")
        self.assertEqual(hidden["observation"]["negotiation"]["permission_terms"], {})
        state = negotiate(s, state, "council", digest(state), self.offer())
        self.assertEqual(faction_packet(s, state, "relief"), hidden)
        self.assertFalse(active_permission(s, state, "visit", "council", "mediators"))
        for invalid in ({"kind": "accept", "id": "offer"},
                        {"kind": "revoke", "id": "offer"},
                        self.offer("duplicate")):
            with self.assertRaises(ValueError):
                negotiate(s, state, "council", digest(state), invalid)
        with self.assertRaises(ValueError):
            self.model(s, state, "relief", {"kind": "accept", "id": "offer"})
        state = self.model(s, state, "mediators", {"kind": "accept", "id": "offer"})
        self.assertTrue(active_permission(s, state, "visit", "council", "mediators"))
        self.assertFalse(active_permission(s, state, "visit", "mediators", "council"))
        self.assertEqual(state["values"], baseline["values"])
        self.assertEqual(state["ledger"], baseline["ledger"])
        self.assertEqual(state["agreement_results"], [])
        self.assertEqual(state["minute"], 0)
        self.assertEqual(recall(observe(s, state, "council"))["outstanding_deadlines"][-1]["kind"], "permission")
        with self.assertRaises(ValueError):
            negotiate(s, state, "council", digest(state), {"kind": "release", "id": "offer"})
        state = negotiate(s, state, "council", digest(state), {"kind": "revoke", "id": "offer"})
        self.assertFalse(active_permission(s, state, "visit", "council", "mediators"))
        self.assertEqual(state["negotiations"]["offer"]["status"], "revoked")
        self.assertEqual(observe(s, state, "mediators")["diplomatic_history"]["council"]["proposals"][0]["status"], "revoked")
        verify_checkpoint(s, state)
        tampered = copy.deepcopy(state)
        tampered["negotiations"]["offer"]["status"] = "active"
        with self.assertRaises(ValueError):
            verify_checkpoint(s, tampered)

    def test_counter_scope_and_expiry(self):
        s = self.scenario()
        state = initialize(s)
        state = negotiate(s, state, "council", digest(state), self.offer())
        counter = {"kind": "counter", "id": "counter", "recipient": "council",
                   "permission": "supervised_visit", "parent": "offer", "due_minute": 10080}
        with self.assertRaises(ValueError):
            self.model(s, state, "mediators", dict(counter, due_minute=20160))
        state = self.model(s, state, "mediators", counter)
        self.assertEqual(state["negotiations"]["offer"]["status"], "countered")
        state = negotiate(s, state, "council", digest(state), {"kind": "accept", "id": "counter"})
        self.assertTrue(active_permission(s, state, "supervised_visit", "council", "mediators"))
        self.assertFalse(active_permission(s, state, "visit", "council", "mediators"))
        state = self.model(s, state, "relief")
        state = advance(s, state)
        self.assertEqual(state["negotiations"]["counter"]["status"], "expired")
        self.assertEqual(state["negotiations"]["counter"]["resolved_minute"], 10080)
        self.assertFalse(active_permission(s, state, "supervised_visit", "council", "mediators"))
        self.assertEqual(state["values"], s["initial"])
        verify_checkpoint(s, state)

    def test_request_release_and_refusal(self):
        s = self.scenario()
        state = initialize(s)
        request = dict(self.offer(), recipient="council")
        state = self.model(s, state, "mediators", request)
        self.assertFalse(active_permission(s, state, "visit", "council", "mediators"))
        state = negotiate(s, state, "council", digest(state), {"kind": "accept", "id": "offer"})
        state = self.model(s, state, "relief")
        state = advance(s, state)
        with self.assertRaises(ValueError):
            self.model(s, state, "mediators", {"kind": "revoke", "id": "offer"})
        state = self.model(s, state, "mediators", {"kind": "release", "id": "offer"})
        self.assertEqual(state["negotiations"]["offer"]["status"], "released")
        self.assertFalse(active_permission(s, state, "visit", "council", "mediators"))
        state = negotiate(s, state, "council", digest(state), self.offer("second"))
        state = negotiate(s, state, "council", digest(state), {"kind": "withdraw", "id": "second"})
        self.assertEqual(state["negotiations"]["second"]["status"], "withdrawn")
        verify_checkpoint(s, state)
        other = initialize(s)
        other = self.model(s, other, "mediators", request)
        other = negotiate(s, other, "council", digest(other), {"kind": "reject", "id": "offer"})
        self.assertEqual(other["negotiations"]["offer"]["status"], "rejected")
        verify_checkpoint(s, other)

    def test_invalid_authority_and_legacy_opt_in(self):
        s = self.scenario()
        state = initialize(s)
        for invalid in (dict(self.offer(), recipient="relief"),
                        dict(self.offer(), permission="invented"),
                        dict(self.offer(), due_minute=30240),
                        dict(self.offer(), transfers=["invented"])):
            with self.assertRaises(ValueError):
                negotiate(s, state, "council", digest(state), invalid)
        self.assertEqual(state, initialize(s))
        for field, value in (("issuer", "unknown"), ("grantee", "council"),
                             ("max_due_minute", 1), ("description", "")):
            malformed = self.scenario()
            malformed["permission_terms"]["visit"][field] = value
            with self.assertRaises(ValueError):
                initialize(malformed)
        disabled = self.scenario()
        del disabled["permission_terms"]
        with self.assertRaises(ValueError):
            initialize(disabled)
        del disabled["dynamic_negotiation"]
        old = initialize(disabled)
        self.assertNotIn("negotiation", observe(disabled, old, "council"))
