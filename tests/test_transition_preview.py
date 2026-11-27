"""Draft transition preparation is actor-local, historical and non-mutating."""
from copy import deepcopy
from pathlib import Path
import unittest

from age_runtime.core.draft_rehearsal import start_rehearsal
from age_runtime.core.private_play import establish_context, pending_factions, model_packet, model_choice, update
from age_runtime.core.runner import digest
from age_runtime.core.transition_preview import transition_preview, continue_rehearsal

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


    def test_confirmed_continuation_preserves_target_baseline(self):
        from age_runtime.core.private_play import briefing, verify
        previous = self.complete()
        original = digest(previous)
        selectors = [{"kind": "established_context", "id": "inc:fiji_room"}]
        preview = transition_preview(ROOT, previous, TARGET, selectors)
        fresh = start_rehearsal(ROOT, TARGET, "fiji")
        session = continue_rehearsal(ROOT, previous, TARGET, selectors, digest(preview))
        self.assertEqual(session["state"]["values"], fresh["state"]["values"])
        self.assertEqual(session["state"]["minute"], 0)
        self.assertEqual(session["header"]["compiled"]["qualification"], "unreviewed-rehearsal")
        self.assertEqual(session["header"]["continuity"]["source_session_digest"], original)
        self.assertEqual(briefing(session)["phase_memory"], preview["selected_history"])
        self.assertFalse(model_packet(session, "shanter")["observation"]["phase_memory"])
        self.assertEqual(digest(previous), original)
        self.assertEqual(session, continue_rehearsal(ROOT, previous, TARGET, selectors, digest(preview)))
        with self.assertRaises(ValueError):
            continue_rehearsal(ROOT, previous, TARGET, selectors, "stale")
        for actor in pending_factions(session):
            packet = model_packet(session, actor)
            session = model_choice(session, actor, {"packet_id": packet["packet_id"], "action": None})
        session = verify(update(session, turns=1))
        self.assertEqual(briefing(session)["phase_memory"], preview["selected_history"])


    def test_multi_phase_memory_and_independent_model_visibility(self):
        from age_runtime.core.private_play import briefing, verify
        from age_runtime.core.transition_preview import model_memory_candidates
        previous = self.complete()
        own = {"kind": "established_context", "id": "inc:fiji_room"}
        other = {"kind": "established_context", "id": "inc:shanter_room"}
        preview = transition_preview(ROOT, previous, TARGET, [own])
        candidates = model_memory_candidates(ROOT, previous, TARGET)
        self.assertIn(other, candidates["selectors_by_actor"]["shanter"])
        self.assertNotIn(own, candidates["selectors_by_actor"]["shanter"])
        with self.assertRaises(ValueError):
            continue_rehearsal(ROOT, previous, TARGET, [own], digest(preview),
                               model_selectors={"shanter": [own]})
        with self.assertRaises(ValueError):
            continue_rehearsal(ROOT, previous, TARGET, [own], digest(preview),
                               model_selectors={"fiji": [own]})
        session = continue_rehearsal(ROOT, previous, TARGET, [own], digest(preview),
                                    model_selectors={"shanter": [other]})
        original = briefing(session)["phase_memory"]
        private = model_packet(session, "shanter")["observation"]["phase_memory"]
        self.assertEqual([r["id"] for r in private], [other["id"]])
        self.assertEqual([r["id"] for r in original], [own["id"]])
        scenario = session["header"]["compiled"]["scenario"]
        while session["state"]["minute"] < scenario["end_minute"]:
            for actor in pending_factions(session):
                packet = model_packet(session, actor)
                session = model_choice(session, actor, {"packet_id": packet["packet_id"], "action": None})
            session = verify(update(session, turns=1))
        catalog = __import__("json").loads(ROOT.read_text())
        target = next(e["id"] for g in catalog["groups"] if g["id"] == "purge"
                      for e in g["scenarios"])
        old = {**own, "source_scenario": SOURCE}
        old_other = {**other, "source_scenario": SOURCE}
        preview2 = transition_preview(ROOT, session, target, [old])
        self.assertIn(old, preview2["candidate_selectors"])
        self.assertNotIn(old_other, preview2["candidate_selectors"])
        later = continue_rehearsal(ROOT, session, target, [old], digest(preview2),
                                   model_selectors={"shanter": [old_other]})
        self.assertEqual(briefing(later)["phase_memory"], original)
        self.assertEqual(model_packet(later, "shanter")["observation"]["phase_memory"], private)
        self.assertEqual(later["header"]["continuity"]["version"], 2)
        self.assertEqual(later["header"]["continuity"]["origins"], [SOURCE])
        verify(later)
