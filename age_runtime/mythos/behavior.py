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
    return result

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
