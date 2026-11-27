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
        self.assertEqual(ids, [1, 2, 3] + list(range(9, 22)))
        self.assertEqual(packet["referee"]["relational_context"]["eleanor"]["current"], current)
        self.assertEqual(packet["history_scope"]["omitted_counts"]["dialogue:eleanor/pc"], 5)
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


    def test_replay_loads_one_source_snapshot_and_preserves_input(self):
        state = mythos.initial("boothbay", 42)
        state = mythos.narrative_step(state, {"kind": "open", "id": "inquiry",
                                               "label": "Investigate the harbor"})
        state = mythos.step(state, "move:Harbor Diner")
        state = mythos.dialogue_step(state, {
            "npc": "eleanor", "speaker": "pc", "claim": "I have a question.",
            "stance": "unstated", "intent": "unstated"})
        state = mythos.establish_step(state, {"details": [{
            "id": "inc:napkin", "kind": "object", "label": "Napkin",
            "description": "A folded napkin.", "basis": "Ordinary diner object"}]})
        state = mythos.narrative_step(state, {"kind": "complete", "id": "inquiry"})
        before = copy.deepcopy(state)
        with patch.object(mythos, "load", wraps=mythos.load) as load:
            mythos.verify(state)
            self.assertEqual(load.call_count, 1)
        self.assertEqual(state, before)
        invalid = copy.deepcopy(state)
        invalid["resources"]["cash_cents"] += 1
        with self.assertRaisesRegex(ValueError, "replay mismatch"):
            mythos.verify(invalid)

    def test_resolution_compatibility_wrapper_preserves_test_ledger(self):
        from age_runtime.mythos import resolution
        state = mythos.initial("boothbay", 42)
        _, rules = mythos.load("boothbay")
        action = next(a for a in rules["actions"] if a["id"] == "inspect_docks")
        direct = copy.deepcopy(state)
        delegated = copy.deepcopy(state)
        self.assertEqual(resolution.resolve(direct, rules, action, mythos.digest),
                         mythos.resolve_dxd(delegated, rules, action))
        self.assertEqual(direct, delegated)

    def test_establishment_dispatch_rejects_unknown_and_mixed_operations(self):
        state = mythos.step(mythos.initial("boothbay", 42), "move:Harbor Diner")
        before = copy.deepcopy(state)
        for request in ({}, {"unknown": {}}, {"details": [], "agreement": {}},
                        ["details"], {"record": {}}):
            with self.subTest(request=request):
                with self.assertRaises(ValueError):
                    mythos.establish_step(state, request)
                self.assertEqual(state, before)


    def test_authored_trial_gm_context_and_choice_timing(self):
        for sid, action in (("castine", "inspect_wharf"),
                            ("ram-island", "maintain_light")):
            with self.subTest(scenario=sid):
                state = mythos.initial(sid, 42)
                before = copy.deepcopy(state)
                public = mythos.view(state)
                packet = mythos.gm_context(state)
                self.assertEqual(packet["audience"], "gm_only")
                self.assertEqual(packet["referee"]["mode"], "authored_actions_with_continuity")
                self.assertTrue(packet["referee"]["capabilities"]["persistent_dialogue"])
                self.assertFalse(packet["referee"]["capabilities"]["npc_agency"])
                self.assertFalse(packet["referee"]["capabilities"]["free_form_proposals"])
                self.assertEqual(packet["referee"]["allowed_actions"],
                                 [a["id"] for a in public["choices"]])
                self.assertEqual(packet["player_surface"]["revision"], public["revision"])
                choice = next(a for a in public["choices"] if a["id"] == action)
                self.assertGreater(choice["seconds"], 0)
                self.assertEqual(choice["minutes"] * 60, choice["seconds"])
                self.assertNotIn("travel_seconds", choice)
                self.assertEqual(player_recap.recap(public)["current_situation"]["description"],
                                 public["opening"])
                packet["player_surface"]["resources"].clear()
                self.assertEqual(state, before)
                after = mythos.step(state, action)
                mythos.verify(after)
                self.assertEqual(mythos.gm_context(after)["player_surface"]["revision"],
                                 mythos.digest(after))

    def test_common_ending_projection_preserves_scenario_flags(self):
        for sid in ("boothbay", "castine", "ram-island"):
            with self.subTest(scenario=sid):
                state = mythos.initial(sid, 42)
                _, rules = mythos.load(sid)
                result = mythos.ending_projection(state, rules, "limit", "observe")
                self.assertEqual(result["reason"], "limit")
                self.assertEqual(result["epilogue"], rules["ending_text"]["limit"])
                self.assertEqual(result["scores"], mythos.scores(state, "observe"))
                for field, flag in rules.get("ending_flags", {}).items():
                    self.assertEqual(result[field], flag in state["flags"])


    def test_cross_trial_continuity_and_encounter_guard(self):
        from age_runtime.mythos import epistemic
        for sid, npc in (("castine", "martha"), ("ram-island", "matteo")):
            with self.subTest(scenario=sid):
                state = mythos.initial(sid, 42)
                _, rules = mythos.load(sid)
                claim = {"npc": npc, "speaker": "pc", "claim": "May we talk again?",
                         "stance": "unstated", "intent": "unstated"}
                with self.assertRaises(ValueError):
                    mythos.dialogue_step(state, claim)
                # Isolate encounter/window guard from authored Test outcomes.
                local = copy.deepcopy(state)
                local["location"] = local["npcs"][npc]["location"]
                with self.assertRaises(ValueError):
                    mythos.dialogue_step(local, claim)
                local["npcs"][npc]["encounters"] = 1
                if sid == "ram-island":
                    local["time"] = "1926-12-21T00:00:00"
                    self.assertFalse(epistemic.conversation_available(local, rules, npc, mythos.npc_available))
                    local["time"] = "1926-11-30T00:00:00"
                before = copy.deepcopy(local)
                answer = dict(claim, speaker=npc, claim="Certainly.",
                              reaction={"emotion": "wary", "significance": "Agreed to speak again."})
                agreement = {"operation": "create", "id": "agr:talk",
                             "kind": "commitment", "npc": npc, "issuer": npc,
                             "terms": "Speak again", "condition": None, "claim_ids": [1, 2]}
                after = mythos.batch_step(local, {"operations": [
                    {"dialogue": claim}, {"dialogue": answer},
                    {"establish": {"agreement": agreement}}]})
                self.assertEqual(local, before)
                for key in ("time", "turn", "flags", "discoveries", "dxd", "resources"):
                    self.assertEqual(after[key], before[key])
                public = mythos.view(after)
                self.assertNotIn("npc_reaction", public["dialogue"][-1])
                self.assertEqual(public["narrative_agreements"][0]["status"], "active")
                gm = mythos.gm_context(after)["referee"]
                self.assertEqual(gm["relational_context"][npc]["current"]["emotion"]["text"], "wary")
                self.assertTrue(gm["contextual_reminders"][npc]["active_agreements"])
                pid = "family_connection" if sid == "castine" else "delivery_account"
                linked = dict(answer, proposition=pid, asserts=True)
                with self.assertRaisesRegex(ValueError, "canonical disclosures"):
                    mythos.dialogue_step(after, linked)

    def test_cross_trial_mundane_establishment_replays(self):
        for sid in ("castine", "ram-island"):
            state = mythos.initial(sid, 42)
            after = mythos.establish_step(state, {"details": [
                {"id": "inc:bench", "kind": "fixture", "label": "Bench",
                 "description": "A plain bench.", "basis": "Mundane local furnishing"}]})
            mythos.verify(after)
            self.assertEqual(after["turn"], state["turn"])
            self.assertEqual(after["flags"], state["flags"])
            self.assertEqual(mythos.view(after)["established_details"][0]["id"], "inc:bench")


    def test_abstract_npc_recovery_actual_castine_replay(self):
        for seed in range(100):
            state = mythos.step(mythos.initial("castine", seed), "inspect_ledger")
            if "ledger" in state["flags"]:
                state = mythos.step(state, "talk_martha")
                break
        else:
            self.fail("No authored Martha encounter")
        state = mythos.dialogue_step(state, {"npc": "martha", "speaker": "pc",
            "claim": "I accuse you of concealing the evidence.", "stance": "unstated",
            "intent": "unstated"})
        episode = {"id": "emo:accusation", "npc": "martha", "claim_ids": [1],
            "emotion": "distress", "intensity": "acute", "expression": "She draws away.",
            "cause": "Actual accusation", "stress": {"martha": "severe"}}
        state = mythos.establish_step(state, {"emotion": episode})
        self.assertEqual(state["npcs"]["martha"]["concerns"]["stress"], 6)
        plan = {"npc": "martha", "mode": "rest", "safe": True,
                "minutes": 20, "basis": "GM establishes an undisturbed private rest interval"}
        planned = mythos.establish_step(state, {"npc_activity": plan})
        self.assertEqual(planned["time"], state["time"])
        self.assertEqual(planned["npcs"]["martha"]["concerns"], state["npcs"]["martha"]["concerns"])
        with self.assertRaises(ValueError):
            mythos.establish_step(planned, {"npc_activity": plan})
        after = mythos.step(planned, "observe")
        expected = copy.deepcopy(state["npcs"]["martha"]["concerns"])
        from age_runtime.core import dxd_conditions
        from datetime import datetime
        minutes = min(20, int((datetime.fromisoformat(after["time"]) -
                              datetime.fromisoformat(planned["time"])).total_seconds()) // 60)
        dxd_conditions.recover(expected, minutes, safe=True, restful=True)
        self.assertEqual(after["npcs"]["martha"]["concerns"], expected)
        self.assertEqual(mythos.step(state, "observe")["npcs"]["martha"]["concerns"],
                         state["npcs"]["martha"]["concerns"])
        mythos.verify(after)
        interrupted = mythos.dialogue_step(planned, {"npc": "martha", "speaker": "pc",
            "claim": "One more question.", "stance": "unstated", "intent": "unstated"})
        self.assertIsNone(interrupted["npcs"]["martha"]["activity_plan"])
        self.assertEqual(mythos.step(interrupted, "observe")["npcs"]["martha"]["concerns"],
                         state["npcs"]["martha"]["concerns"])
        mythos.verify(interrupted)

    def test_coarse_recovery_caps_long_interval_and_preserves_unsafe_stress(self):
        from age_runtime.mythos import npc_time
        from age_runtime.core import dxd_conditions
        from datetime import datetime, timedelta
        state = mythos.initial("ram-island", 42)
        _, rules = mythos.load("ram-island")
        npc = state["npcs"]["matteo"]
        dxd_conditions.add(npc["concerns"], fatigue=20, stress=12, weariness=12)
        start = datetime.fromisoformat(state["time"])
        npc["activity_plan"] = {"at": start.isoformat(),
            "until": (start + timedelta(minutes=10)).isoformat(),
            "location": npc["location"], "safe": False, "mode": "rest"}
        expected = copy.deepcopy(npc["concerns"])
        dxd_conditions.recover(expected, 10, safe=False, restful=True)
        npc_time.advance_abstract(state, rules, start, start + timedelta(days=5))
        self.assertEqual(npc["concerns"], expected)
        self.assertEqual(npc["concerns"]["stress"], 12)
        self.assertIsNone(npc["activity_plan"])

    def test_authored_social_demeanor_replay_and_duplicate_guard(self):
        for seed in range(100):
            state = mythos.step(mythos.initial("castine", seed), "inspect_ledger")
            if "ledger" in state["flags"]:
                state = mythos.step(state, "talk_martha")
                break
        else:
            self.fail("No authored encounter")
        state = mythos.dialogue_step(state, {"npc": "martha", "speaker": "pc",
            "claim": "I consider you a dishonest witness.", "stance": "unstated",
            "intent": "unstated"})
        harm = {"npc": "martha", "claims": [1], "kind": "harm",
                "basis": "Actual personal insult"}
        before = copy.deepcopy(state)
        after = mythos.establish_step(state, {"social_demeanor": harm})
        self.assertLess(after["relationships"]["martha"], before["relationships"]["martha"])
        for key in ("time", "turn", "flags", "discoveries", "dxd", "resources"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after["relationship_changes"][-1]["claims"], [1])
        self.assertEqual(mythos.gm_context(after)["referee"]["consequential_demeanor"]["martha"][-1]["kind"], "harm")
        self.assertIn("demeanor", mythos.view(after)["contacts"][0])
        with self.assertRaises(ValueError):
            mythos.establish_step(after, {"social_demeanor": harm})
        mythos.verify(after)

    def test_native_demeanor_rolling_limits_across_coarse_time(self):
        from datetime import datetime, timedelta
        state = mythos.initial("ram-island", 42)
        for _ in range(4):
            mythos.change_demeanor(state, "matteo", -1)
        self.assertEqual(state["relationships"]["matteo"], -3)
        for _ in range(4):
            mythos.change_demeanor(state, "matteo", 1)
        self.assertEqual(state["relationships"]["matteo"], -2)
        state["time"] = (datetime.fromisoformat(state["time"]) + timedelta(days=8)).isoformat()
        mythos.change_demeanor(state, "matteo", 1)
        self.assertEqual(state["relationships"]["matteo"], -1)
        state["time"] = (datetime.fromisoformat(state["time"]) + timedelta(days=31)).isoformat()
        mythos.change_demeanor(state, "matteo", 3)
        self.assertEqual(state["relationships"]["matteo"], 2)

    def test_scoped_objectives_and_beliefs_from_actual_castine_encounter(self):
        for seed in range(100):
            state = mythos.step(mythos.initial("castine", seed), "inspect_ledger")
            if "ledger" in state["flags"]:
                state = mythos.step(state, "talk_martha")
                break
        else:
            self.fail("No eligible authored encounter")
        request = {"npc": "martha", "speaker": "pc", "claim": "Perhaps Imogen left voluntarily.",
                   "stance": "unstated", "intent": "unstated"}
        state = mythos.dialogue_step(state, request)
        cid = state["dialogue"][-1]["id"]
        objective = {"operation": "create", "id": "goal:account", "npc": "martha",
                     "goal": "Understand the inquiry", "priority": "normal",
                     "intention": "Consider the suggestion", "basis": "Actual inquiry",
                     "sources": [{"kind": "claim", "id": cid}]}
        before = copy.deepcopy(state)
        state = mythos.batch_step(state, {"operations": [
            {"establish": {"npc_objective": objective}},
            {"establish": {"hypothesis": {"id": "hyp:departure", "npc": "martha",
                                           "text": "Imogen left voluntarily.", "source": cid}}},
            {"establish": {"belief_revision": {"npc": "martha", "proposition": "hyp:departure",
                "stance": "doubts", "asserts": True, "sources": [cid], "basis": "Uncertain account"}}}]})
        for key in ("time", "turn", "flags", "discoveries", "dxd", "relationships"):
            self.assertEqual(state[key], before[key])
        self.assertNotIn("favor", state["npcs"]["martha"])
        public = mythos.view(state)
        self.assertNotIn("npc_objectives", public)
        self.assertNotIn("dynamic_propositions", public)
        ref = mythos.gm_context(state)["referee"]
        self.assertEqual(ref["npc_agency"]["martha"]["objectives"][0]["id"], "goal:account")
        self.assertNotIn("zebediah", ref["npc_agency"])
        self.assertNotIn("favor", ref["npc_agency"]["martha"])
        self.assertEqual(ref["npc_agency"]["martha"]["social_tests"], [])
        self.assertNotIn("npc_social_tests", state)
        self.assertIn("emotional_context", ref)
        self.assertIn("npc_temporal", ref)
        self.assertIn("consequential_demeanor", ref)
        mythos.verify(state)
        with self.assertRaises(ValueError):
            mythos.establish_step(state, {"npc_objective": dict(objective, id="goal:other",
                sources=[{"kind": "observation", "id": "missing"}])})
        with self.assertRaises(ValueError):
            mythos.establish_step(state, {"npc_social_test": {
                "id": "social:test", "claim": cid, "basis": "Unsupported Test"}})
