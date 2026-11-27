"""NPC-specific behavioral evidence, with subjective recognition kept separate."""
import copy
import re

def evidence(state, npc):
    result = {}
    for c in state.get("dialogue", []):
        if c["speaker"] == "pc" and c["listener"] == npc:
            result["claim:" + str(c["id"])] = {"kind": "utterance", "text": c["claim"],
                "turn": c["turn"], "at": c["at"], "location": c["location"]}
    for o in state.get("action_observations", []):
        if o["npc"] == npc and o["kind"] == "witnessed" and o["actor"] == "pc":
            result[o["id"]] = {"kind": "witnessed_action", "object": o["object"],
                "outcome": o["outcome"], "turn": o["turn"], "at": o["at"], "location": o["location"]}
    for o in state.get("routine_observations", []):
        if o["npc"] == npc:
            result[o["id"]] = {k: copy.deepcopy(v) for k, v in o.items()
                               if k not in ("id", "npc", "basis")}
    return result

def record_routine(state, rules, request, npc_available, text):
    if not rules.get("routine_observations") or not isinstance(request, dict) or set(request) != {"id", "npc", "kind", "basis"}:
        raise ValueError("invalid routine observation")
    oid, npc, kind = request["id"], request["npc"], request["kind"]
    if not isinstance(oid, str) or not re.fullmatch(r"routine:[a-z][a-z0-9_]{0,63}", oid):
        raise ValueError("invalid routine observation identity")
    if not isinstance(npc, str) or npc not in state["npcs"] or state["npcs"][npc]["location"] != state["location"] or not npc_available(state, rules, {"npc": npc, "location": state["location"]}):
        raise ValueError("routine observation requires available local NPC")
    # Only the latest completed native action is eligible. No retrospective
    # attribution based on the global movement history.
    last = state["last_result"] or {}
    source = state.get("routine_source")
    if not source or source["turn"] != state["turn"] or source["location"] != state["location"] or npc not in source["eligible_observers"]:
        raise ValueError("no contemporaneous routine source for NPC")
    if kind == "arrival":
        trip = last.get("transition")
        if not trip or trip["turn"] != state["turn"] or trip["nodes"][-1] != state["location"] or trip["arrival"] != state["time"] or last.get("interrupted"):
            raise ValueError("arrival observation requires just-completed arrival")
        detail = {"text": "Arrived at " + state["location"]}
    elif kind == "activity":
        label = rules["routine_observations"]["activities"].get(last.get("action"))
        if not label or not last.get("success") or last.get("interrupted") or npc not in source["activity_observers"]:
            raise ValueError("activity observation requires reviewed completed activity")
        detail = {"text": label}
    else:
        raise ValueError("invalid routine observation kind")
    ledger = state["routine_observations"]
    if len(ledger) >= 256 or any(o["id"] == oid or (o["npc"], o["turn"], o["kind"]) == (npc, state["turn"], kind) for o in ledger):
        raise ValueError("duplicate routine observation or record limit")
    ledger.append({"id": oid, "npc": npc, "kind": kind, **detail,
                   "turn": state["turn"], "at": state["time"], "location": state["location"],
                   "basis": text(request["basis"], 240)})

def record(state, rules, request, npc_available, text):
    if not rules.get("behavioral_recognition") or not isinstance(request, dict) or set(request) != {"id", "npc", "kind", "evidence", "interpretation"}:
        raise ValueError("invalid behavioral recognition")
    rid, npc, kind, refs = (request[k] for k in ("id", "npc", "kind", "evidence"))
    if not isinstance(rid, str) or not re.fullmatch(r"pat:[a-z][a-z0-9_]{0,63}", rid):
        raise ValueError("invalid behavioral recognition identity")
    if not isinstance(npc, str) or npc not in state["npcs"] or state["npcs"][npc]["location"] != state["location"] or not npc_available(state, rules, {"npc": npc, "location": state["location"]}):
        raise ValueError("recognition requires available local NPC")
    if kind not in ("salient", "recurring"):
        raise ValueError("invalid recognition kind")
    if not isinstance(refs, list) or not 1 <= len(refs) <= 8 or any(not isinstance(r, str) for r in refs) or len(set(refs)) != len(refs):
        raise ValueError("invalid behavioral evidence references")
    known = evidence(state, npc)
    if any(r not in known for r in refs):
        raise ValueError("behavioral evidence not observed by NPC")
    if kind == "recurring" and len({known[r]["turn"] for r in refs}) < 2:
        raise ValueError("recurrence requires distinct turns")
    ledger = state["behavioral_recognition"]
    interpretation = text(request["interpretation"], 240)
    if len(ledger) >= 256 or any(e["id"] == rid or (e["npc"] == npc and e["kind"] == kind and set(e["evidence"]) == set(refs)) for e in ledger):
        raise ValueError("duplicate recognition or record limit")
    ledger.append({"id": rid, "npc": npc, "kind": kind, "evidence": list(refs),
                   "interpretation": interpretation, "at": state["time"], "turn": state["turn"]})

def projection(state, participants):
    result = {}
    for npc in sorted(participants):
        known = evidence(state, npc)
        recent = sorted(known, key=lambda r: known[r]["turn"])[-8:]
        patterns = [e for e in state.get("behavioral_recognition", []) if e["npc"] == npc][-8:]
        refs = list(dict.fromkeys(recent + [r for p in patterns for r in p["evidence"]]))
        result[npc] = {"evidence": {r: copy.deepcopy(known[r]) for r in refs},
                       "interpretations": copy.deepcopy(patterns),
                       "observed_turns": len({e["turn"] for e in known.values()})}
    return result
