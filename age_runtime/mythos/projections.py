"""Player and referee projections; no state transitions or persistence."""
import copy
from datetime import datetime

from age_runtime.mythos import (
    spatial, pacing, events as narrative_events, proposals, beats, continuity,
    nominations, hooks, epistemic, establishment, agreements, locks,
    timed_details, emotions, reminders, npc_time, action_observations,
    behavior, expectations, npc_travel, npc_agency,
)
from age_runtime.core import dxd_conditions, dxd_morale, dxd_commitment

def player_view(state, rules, legal, npc_available, digest, demeanor_labels, *, full_history=False):
    scene = rules.get("scene")
    scene_view = {} if not scene else {"scene": {"description": scene["locations"].get(state["location"], ""),
        "pressure": [p["text"] for p in scene.get("pressure", []) if p["flag"] in state["flags"]],
        "cues": [a["label"] for a in legal if a.get("location", state["location"]) == state["location"]]}}
    if scene and "spatial" in rules:
        config = rules["spatial"]
        scene_view["scene"]["zone"] = config["nodes"][state["location"]]["zone"]
        scene_view["scene"]["routes"] = [r for r in spatial.reachable(config, state) if r["seconds"] <= (datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds()] if not state["ending"] else []
        scene_view["scene"]["contacts_here"] = [p["name"] for nid, p in state["npcs"].items() if p["encounters"] and p["location"] == state["location"] and npc_available(state, rules, {"npc": nid, "location": state["location"]})]
    if "pacing" in state:
        scene_view["pacing"] = pacing.projection(state, rules)
    if rules.get("danger_beats"):
        scene_view["danger"] = beats.available(state, rules)
    if "commitments" in state["dxd"]:
        scene_view["emotional_commitments"] = copy.deepcopy(state["dxd"]["commitments"])
    if "established_details" in state:
        scene_view["established_details"] = establishment.projection(state)
    if "agreement_history" in state:
        scene_view["narrative_agreements"] = agreements.public_projection(state)
    if "dialogue" in state:
        scene_view["dialogue"] = epistemic.public_projection(state)
    if "local_records" in state:
        scene_view["local_records"] = copy.deepcopy(state["local_records"] if full_history else state["local_records"][-8:])
    if "narrative_events" in state:
        scene_view["event_pressure"] = narrative_events.projection(state, rules)
    if "activity" in state["dxd"]:
        clock = state["dxd"]["activity"]
        scene_view["activity"] = {k: clock[k] for k in ("status", "awake_seconds", "limit_seconds", "overdue_seconds", "sleep_seconds", "required_sleep_seconds", "activity", "pending_sleep_seconds")}
    if rules.get("automatic_emphasis"):
        scene_view["character_emphasis_xp"] = state["dxd"].get("xp", 0)
        scene_view["latest_emphasis_award"] = next((copy.deepcopy(e) for e in reversed(state["dxd"].get("emphasis_awards", [])) if e["turn"] == state["turn"]), None)
    return copy.deepcopy(scene_view | {k: state[k] for k in ("scenario","time","location","turn","discoveries","observations","ending","last_result")} | {
        "inventory": [item for item in state["inventory"] if not item.startswith(("$", "Flask"))],
        "resources": state["resources"],
        "setting": rules.get("setting", "Fear!"),
        "memories": [x["memory"] for x in state.get("dxd", {}).get("inspirations", [])],
        "memory_prompt": next(({"event": x["action"], "basis": x["basis"]}
            for x in state["dxd"]["inspirations"] if x["turn"] == state["turn"]
            and x["source"] == "authored"), None),
        "contacts": [{"name": p["name"], "role": p["public_role"],
                      **({"demeanor": demeanor_labels[dxd_commitment.effective_demeanor(state, nid) + 6]} if rules.get("demeanor") else {}),
                      "encounters": p["encounters"], "last_contact": p["last_contact"]}
                     for nid, p in state["npcs"].items() if p["encounters"]],
        "condition": dict(dxd_conditions.describe(state["dxd"]["concerns"]),
                          fear=dxd_morale.describe(state["dxd"]["morale"])),
        "revision": digest(state), "opening": rules["opening"] if not state["turn"] else None,
        "choices": [{"id": a["id"], "label": a["label"], **({"minutes": a["duration_seconds"] / 60, "seconds": a["duration_seconds"], "destination": a.get("location", state["location"]), "travel_minutes": a["route"]["minutes"], "travel_seconds": a["route"]["seconds"]} if "spatial" in rules else {}), **({"preparation_saved_seconds": a["preparation_saved_seconds"]} if a.get("preparation_saved_seconds") else {})} for a in legal]})

def referee_view(state, story, rules, legal, npc_available, digest, demeanor_labels, *, compact=False):
    """Bounded referee packet; never render directly as player narration."""
    if not rules.get("gm_proposals"):
        raise ValueError("GM context not yet supported for scenario")
    public = player_view(state, rules, legal, npc_available, digest, demeanor_labels)
    # Keep complete authoritative history in the checkpoint, not every prompt.
    recent = {k: public[k] for k in ("scenario", "time", "location", "turn",
              "ending", "last_result", "condition", "resources", "revision", "choices")}
    recent.update({k: public[k] for k in ("scene", "pacing", "activity", "event_pressure", "local_records", "danger", "emotional_commitments", "established_details", "narrative_agreements") if k in public})
    recent["observations"] = state["observations"][-8:]
    recent["discoveries"] = list(state["discoveries"])
    recent["contacts"] = public["contacts"]
    recent["inventory"] = public["inventory"]
    recent["memories"] = public["memories"][-4:]
    recent["memory_prompt"] = public["memory_prompt"]
    recent["opening"] = public["opening"]
    if "pacing" in recent and recent["pacing"]["current_spotlight"]:
        active = copy.deepcopy(recent["pacing"]["current_spotlight"])
        active["activities"] = active["activities"][-6:]
        recent["pacing"]["current_spotlight"] = active
    pc = state["dxd"]
    local = [a for a in legal if a.get("location", state["location"]) == state["location"]]
    relevant = {a["npc"] for a in local if "npc" in a}
    # Dialogue does not end when the last mechanical topic is spent.
    # Only anchored, currently available participants can converse without
    # an action. An unanchored contact still needs an authorized encounter.
    conversational = {key for key, npc in state["npcs"].items()
                      if npc["location"] == state["location"]
                      and npc_available(state, rules, {"npc": key, "location": state["location"]})}
    if state["ending"] or pc.get("activity", {}).get("status") == "asleep":
        conversational = set()
    relevant |= conversational
    packet = {"audience": "gm_only", "source_revision": state["source"],
            "player_surface": recent,
            "referee": {
                "location_basis": next(({"features": x["features"], "dangers": x["dangers"]}
                    for x in story["locations"] if x["name"] == state["location"]), None),
                "participants": [{"id": key, "name": state["npcs"][key]["name"],
                                  "motivation": state["npcs"][key]["motivation"],
                                  "known_topics": state["npcs"][key]["known_topics"],
                                  "disclosed": state["npcs"][key]["disclosed"],
                                  "secret": state["npcs"][key]["secret"],
                                  "location": state["npcs"][key]["location"],
                                  "conversation_available": key in conversational,
                                  "encounters": state["npcs"][key]["encounters"],
                                  "last_contact": state["npcs"][key]["last_contact"],
                                  "demeanor": state["relationships"].get(key),
                                  "source_traits": copy.deepcopy(state["npcs"][key]["traits"]),
                                  "local_actions": [a["id"] for a in local if a.get("npc") == key],
                                  "skills": copy.deepcopy(state["npcs"][key].get("skills", {})),
                                  "traits": copy.deepcopy(state["npcs"][key].get("dxd_traits", {}))}
                                 for key in sorted(relevant)],
                **({"dialogue_context": epistemic.referee_projection(state, relevant)} if "dialogue" in state else {}),
                "propositions": epistemic.proposition_projection(state, rules, relevant),
                **({"npc_temporal": npc_time.projection(state, state['npcs'] if rules.get('npc_lifecycle') else conversational)} if rules.get("npc_temporal") else {}),
                **({"contextual_reminders": reminders.projection(state, conversational)} if rules.get("epistemic_dialogue") else {}),
                **({"emotional_context": emotions.projection(state, conversational)} if rules.get("interpersonal_duress") else {}),
                **({"next_dialogue_id": len(state.get("dialogue", [])) + 1} if rules.get("narrative_batch") else {}),
                **({"timed_detail_events": timed_details.projection(state)} if rules.get("timed_detail_event") else {}),
                **({"npc_travel": npc_travel.projection(state)} if rules.get("npc_travel") else {}),
                **({"npc_agency": npc_agency.projection(state)} if rules.get("npc_agency") else {}),
                **({"narrative_locks": locks.projection(state, rules, npc_available, establishment.local_entities)} if rules.get("narrative_locks") else {}),
                **({"established_details": establishment.referee_projection(state)} if "established_details" in state else {}),
                **({"object_actions": copy.deepcopy(state["object_actions"][-8:])} if "object_actions" in state else {}),
                **({"action_observations": action_observations.projection(state, conversational)} if rules.get("action_observations") else {}),
                **({"consequential_demeanor": {nid: copy.deepcopy([e for e in state["relationship_changes"] if e["npc"] == nid and e.get("source") in ("consequential_conduct", "social_conduct")][-6:]) for nid in sorted(conversational)}} if rules.get("consequential_demeanor") else {}),
                **({"behavioral_context": behavior.projection(state, conversational)} if rules.get("behavioral_recognition") else {}),
                **({"routine_source": copy.deepcopy(state["routine_source"])} if rules.get("routine_observations") else {}),
                **({"npc_expectations": expectations.projection(state, conversational),
                    "literary_synthesis": "Before composing significant NPC responses, reconcile observed conduct, expectations, attachments, emotional history, current Concerns, Demeanor and competing motivations. Braid relevant influences into speech and physical behavior with concise contextual reminders. Do not erase prior conflict merely because Stress recovered or invent shared history."} if rules.get("npc_expectations") else {}),
                **({"relational_context": epistemic.relational_projection(state, relevant)} if rules.get("relational_continuity") else {}),
                "concerns": copy.deepcopy(pc["concerns"]),
                "attributes": dict(pc["attributes"]), "skills": copy.deepcopy(pc["skills"]),
                "traits": copy.deepcopy(pc["traits"]),
                "character_profile": copy.deepcopy(state.get("character_profiles", {}).get("pc")),
                "addiction_check": copy.deepcopy(pc.get("addiction_check")),
                "addicted": pc.get("addicted", False),
                "favor": pc["favor"],
                "commitment_options": [{"action": a["id"], "context": a["npc"], "level": 1} for a in legal if dxd_commitment.eligible(state, rules, a)],
                "modifier_nominations": nominations.projection(state, rules, legal, npc_available),
                "character_hooks": {a["id"]: h for a in legal if (h := hooks.offers(state, rules, a))},
                "persistent_circumstances": {a["id"]: h for a in legal if (h := hooks.circumstances(state, rules, a))},
                "character_emphasis_xp": pc.get("xp", 0),
                "narrative_functions": continuity.projection(state, rules, legal),
                "local_capabilities": proposals.local_capabilities(state, rules, npc_available),
                "approaches": {a["id"]: sorted(rules["gm_proposals"][a["id"]])
                               for a in legal if a["id"] in rules.get("gm_proposals", {})},
                "clocks": [{"id": key, "name": cfg["name"], "source": cfg["source"],
                            "segments": cfg["segments"], **state["narrative_events"]["clocks"][key]}
                           for key, cfg in rules.get("event_clocks", {}).items()
                           if not state["narrative_events"]["clocks"][key]["resolved"]],
                "last_test": {k: pc["tests"][-1]["result"][k] for k in ("passed", "margin", "dos", "dof")}
                             if pc["tests"] and pc["tests"][-1]["turn"] == state["turn"] else None}}
    if compact:
        compact_history(packet)
    return copy.deepcopy(packet)


def compact_history(packet):
    """Bound verbose historical lists, not current authority or evidence IDs."""
    ref = packet["referee"]
    omitted = {}
    def tail(records, count, key):
        if len(records) > count:
            omitted[key] = len(records) - count
            return records[-count:]
        return records
    if "dialogue_context" in ref:
        # Bound per actor pair rather than globally starving a quieter NPC.
        groups = {}
        for entry in ref["dialogue_context"]:
            pair = tuple(sorted((entry["speaker"], entry["listener"])))
            groups.setdefault(pair, []).append(entry)
        selected = []
        for pair, entries in sorted(groups.items()):
            selected.extend(tail(entries, 12, "dialogue:" + "/".join(pair)))
        # Keep earlier claims referenced by current agreements and their
        # resolutions. Full GM context remains available for other sources.
        required = {i for a in packet["player_surface"].get("narrative_agreements", [])
                    for field in ("claim_ids", "resolution_claim_ids")
                    for i in a.get(field, [])}
        # Retain the evidence behind current relationship fields and
        # the selected contextual reminders, even when old.
        required.update(value["claim_id"]
                        for context in ref.get("relational_context", {}).values()
                        for value in context["current"].values())
        required.update(cue["claim_id"]
                        for context in ref.get("contextual_reminders", {}).values()
                        for cue in context["utterances"])
        selected_ids = {e["id"] for e in selected} | required
        ref["dialogue_context"] = [e for e in ref["dialogue_context"]
                                   if e["id"] in selected_ids]
        # Report the actual count after preserving referenced claims.
        for pair, entries in groups.items():
            key = "dialogue:" + "/".join(pair)
            count = sum(e["id"] not in selected_ids for e in entries)
            if count:
                omitted[key] = count
            else:
                omitted.pop(key, None)
    for npc, context in ref.get("relational_context", {}).items():
        context["experiences"] = tail(context["experiences"], 8, "relationship:" + npc)
    packet["history_scope"] = {"mode": "compact", "omitted_counts": omitted,
                               "full_context": "game.py gm SESSION"}
