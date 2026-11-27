"""Draft transition preparation is actor-local, historical and non-mutating."""
from copy import deepcopy
from pathlib import Path
import unittest

from age_runtime.core.draft_rehearsal import start_rehearsal
from age_runtime.core.private_play import establish_context, pending_factions, model_packet, model_choice, update
from age_runtime.core.runner import digest
from age_runtime.core.transition_preview import transition_preview

ROOT = Path(__file__).resolve().parents[1] / "scenarios/sh44ser/conflagration/inventory.json"
SOURCE = "mainlander-ingress-regional-draft"
TARGET = "early-reconstruction-regional-draft"


class TransitionPreviewTests(unittest.TestCase):
    def complete(self):
        session = start_rehearsal(ROOT, SOURCE, "fiji")
        session = establish_context(session, digest(session), {"details": [
            {"id": "inc:fiji_room", "kind": "facility_detail", "label": "Reception room",
             "description": "A small reception room.", "audience": ["fiji"], "basis": "Fixture."},
            {"id": "inc:shanter_room", "kind": "facility_detail", "label": "Office",
             "description": "A separate office.", "audience": ["shanter"], "basis": "Fixture."}]})
        for _ in range(4):
            for actor in pending_factions(session):
                packet = model_packet(session, actor)
                session = model_choice(session, actor, {"packet_id": packet["packet_id"], "action": None})
            session = update(session, turns=1)
        return session

    def test_preview_and_select_own_history(self):
        session = self.complete()
        before = deepcopy(session)
        preview = transition_preview(ROOT, session, TARGET)
        own = {"kind": "established_context", "id": "inc:fiji_room"}
        hidden = {"kind": "established_context", "id": "inc:shanter_room"}
        self.assertIn(own, preview["candidate_selectors"])
        self.assertNotIn(hidden, preview["candidate_selectors"])
        selected = transition_preview(ROOT, session, TARGET, [own])
        self.assertEqual([r["id"] for r in selected["selected_history"]], ["inc:fiji_room"])
        self.assertGreater(selected["gap_days"], 0)
        self.assertFalse(selected["approved"])
        self.assertFalse(selected["registered"])
        self.assertEqual(session, before)
        for selectors in ([hidden], [own, own], []):
            with self.assertRaises(ValueError):
                transition_preview(ROOT, session, TARGET, selectors)

    def test_reject_incomplete_and_backward_transition(self):
        with self.assertRaises(ValueError):
            transition_preview(ROOT, start_rehearsal(ROOT, SOURCE, "fiji"), TARGET)
        session = self.complete()
        for target in (SOURCE, "fallout-coalition-relief-draft"):
            with self.assertRaises(ValueError):
                transition_preview(ROOT, session, target)
