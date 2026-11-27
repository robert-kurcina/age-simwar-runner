"""Consolidation regressions: no new state format, mechanics or narrative ledger."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from age_runtime.mythos import mythos, player_recap, projections


class NarrativeConsolidationTests(unittest.TestCase):
    def test_public_projection_is_detached_for_every_trial(self):
        for sid in ("boothbay", "castine", "ram-island"):
            with self.subTest(scenario=sid):
                state = mythos.initial(sid, 42)
                before = copy.deepcopy(state)
                public = mythos.view(state)
                public["discoveries"].append("not committed")
                public["observations"].append("not committed")
                public["resources"].clear()
                public["choices"].clear()
                if public.get("pacing", {}).get("current_spotlight"):
                    public["pacing"]["current_spotlight"]["activities"].clear()
                self.assertEqual(state, before)
                mythos.verify(state)

    def test_gm_projection_reuses_one_rules_load_and_action_computation(self):
        state = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        state = mythos.narrative_step(state, {"kind": "open", "id": "inquiry",
                                               "label": "Ask about the missing man"})
        before = copy.deepcopy(state)
        with patch.object(mythos, "load", wraps=mythos.load) as load, \
                patch.object(mythos, "options", wraps=mythos.options) as options:
            packet = mythos.gm_context(state)
            self.assertEqual(load.call_count, 1)
            self.assertEqual(options.call_count, 1)
        self.assertEqual(packet["player_surface"]["revision"], mythos.digest(state))
        packet["player_surface"]["resources"].clear()
        packet["player_surface"]["pacing"]["current_spotlight"]["label"] = "changed"
        for participant in packet["referee"]["participants"]:
            participant["known_topics"].clear()
        self.assertEqual(state, before)

    def test_recall_full_history_preserves_bounded_normal_view(self):
        # Isolate the presentation window from local proposal eligibility.
        # These are synthetic player-origin records, not a replay fixture.
        state = mythos.initial("boothbay", 42)
        state["local_records"] = [
            {"kind": "survey", "target": "Harbor Docks",
             "turn": i, "at": state["time"], "passed": True, "effect": 1,
             "established": "survey_completed",
             "label": "old record" if i == 0 else "other record"}
            for i in range(12)]
        before = copy.deepcopy(state)
        ordinary = mythos.view(state)
        history = mythos.view(state, full_history=True)
        self.assertEqual(len(ordinary["local_records"]), 8)
        self.assertEqual(len(history["local_records"]), 12)
        self.assertEqual(player_recap.recall(ordinary, "old record")["total"], 0)
        found = player_recap.recall(history, "old record")
        self.assertEqual(found["matches"][0]["record"]["turn"], 0)
        self.assertEqual(ordinary["revision"], history["revision"])
        self.assertEqual(state, before)

    def test_compact_history_retains_older_agreement_and_current_reaction(self):
        # Synthetic projection isolates compaction, including a quieter NPC.
        claims = [{"id": i, "speaker": "pc", "listener": "eleanor"} for i in range(1, 21)]
        claims.append({"id": 21, "speaker": "pc", "listener": "elias"})
        current = {"emotion": {"text": "uneasy", "claim_id": 2}}
        packet = {
            "player_surface": {"narrative_agreements": [
                {"claim_ids": [1], "resolution_claim_ids": [3]}]},
            "referee": {"dialogue_context": claims,
                        "relational_context": {"eleanor": {
                            "current": copy.deepcopy(current),
                            "experiences": [{"claim_id": i} for i in range(1, 21)]}}}}
        projections.compact_history(packet)
        ids = [entry["id"] for entry in packet["referee"]["dialogue_context"]]
        self.assertEqual(ids, [1, 3] + list(range(9, 22)))
        self.assertEqual(packet["referee"]["relational_context"]["eleanor"]["current"], current)
        self.assertEqual(packet["history_scope"]["omitted_counts"]["dialogue:eleanor/pc"], 6)
        self.assertEqual(len(packet["referee"]["relational_context"]["eleanor"]["experiences"]), 8)

    def test_single_copy_batch_matches_sequential_steps_and_replay(self):
        state = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        before = copy.deepcopy(state)
        claim = {"npc": "eleanor", "speaker": "pc", "claim": "I have a question.",
                 "stance": "unstated", "intent": "unstated"}
        detail = {"details": [{"id": "inc:napkin", "kind": "object", "label": "Napkin",
                               "description": "A folded napkin.", "basis": "Ordinary diner object"}]}
        operations = [{"dialogue": claim}, {"establish": detail}]
        expected = mythos.establish_step(mythos.dialogue_step(state, claim), detail)
        with patch.object(mythos, "load", wraps=mythos.load) as load:
            actual = mythos.batch_step(state, {"operations": operations})
            self.assertEqual(load.call_count, 1)
        self.assertEqual(actual, expected)
        self.assertEqual(state, before)
        mythos.verify(actual)
        with self.assertRaises(ValueError):
            mythos.batch_step(state, {"operations": operations + [{"dialogue": claim}]})
        self.assertEqual(state, before)

    def test_transaction_does_not_save_if_public_projection_fails(self):
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "session.json"
            opening = mythos.start("boothbay", path, 42)
            before = path.read_bytes()
            with patch.object(mythos, "view", side_effect=ValueError("projection failure")):
                with self.assertRaisesRegex(ValueError, "projection failure"):
                    mythos.act(path, "inspect_docks", opening["revision"])
            self.assertEqual(path.read_bytes(), before)
            after = mythos.act(path, "inspect_docks", opening["revision"])
            self.assertNotEqual(after["revision"], opening["revision"])
            self.assertEqual(mythos.inspect(path), after)
