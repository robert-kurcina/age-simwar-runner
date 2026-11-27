"""Prospective NPC expectations and evidence-backed reassessment."""
import copy
import re
from age_runtime.mythos import behavior

def record(state, rules, request, npc_available, text):
    if not rules.get("npc_expectations") or not isinstance(request, dict):
        raise ValueError("NPC expectations unavailable")
    op = request.get("operation")
    fields = {"operation", "id", "npc", "pattern", "expectation"} if op == "create" else {"operation", "id", "npc", "outcome", "evidence", "interpretation"}
    if op not in ("create", "assess") or set(request) != fields:
        raise ValueError("invalid expectation fields")
    eid, npc = request["id"], request["npc"]
    if not isinstance(eid, str) or not re.fullmatch(r"exp:[a-z][a-z0-9_]{0,63}", eid):
        raise ValueError("invalid expectation identity")
    if not isinstance(npc, str) or npc not in state["npcs"] or state["npcs"][npc]["location"] != state["location"] or not npc_available(state, rules, {"npc": npc, "location": state["location"]}):
        raise ValueError("expectation requires available local NPC")
    ledger = state["npc_expectations"]
    if len(ledger) >= 256:
        raise ValueError("expectation record limit")
    current = project(state)
    event = {"operation": op, "id": eid, "npc": npc, "turn": state["turn"], "at": state["time"], "sequence": len(state["history"])}
    if op == "create":
        pattern = next((p for p in state["behavioral_recognition"] if p["id"] == request["pattern"] and p["npc"] == npc), None)
        if not pattern or pattern["kind"] != "recurring" or eid in current:
            raise ValueError("expectation requires own recurring pattern and new identity")
        if any(e["npc"] == npc and e["pattern"] == pattern["id"] and e["status"] == "pending" for e in current.values()):
            raise ValueError("pattern already has pending expectation")
        event.update(pattern=pattern["id"], expectation=text(request["expectation"], 240),
                     prior_evidence=list(behavior.evidence(state, npc)))
    else:
        old = current.get(eid)
        if not old or old["npc"] != npc or old["status"] != "pending":
            raise ValueError("expectation not pending for NPC")
        refs = request["evidence"]
        if request["outcome"] not in ("confirmed", "contradicted", "inconclusive"):
            raise ValueError("invalid assessment")
        known = behavior.evidence(state, npc)
        if not isinstance(refs, list) or not 1 <= len(refs) <= 8 or any(not isinstance(r, str) for r in refs) or len(set(refs)) != len(refs):
            raise ValueError("invalid assessment evidence")
        if any(r not in known or r in old["prior_evidence"] for r in refs):
            raise ValueError("assessment requires new observed evidence")
        event.update(outcome=request["outcome"], evidence=list(refs), interpretation=text(request["interpretation"], 240))
    ledger.append(event)

def project(state):
    result = {}
    for e in state.get("npc_expectations", []):
        if e["operation"] == "create":
            result[e["id"]] = dict(copy.deepcopy(e), status="pending")
        else:
            result[e["id"]].update(status=e["outcome"], assessment=copy.deepcopy(e))
    return result

def projection(state, participants):
    result = {}
    current = project(state)
    for npc in sorted(participants):
        entries = [e for e in current.values() if e["npc"] == npc]
        # Keep pending expectations visible even when older than resolved ones.
        selected = [e for e in entries if e["status"] == "pending"] + [e for e in entries if e["status"] != "pending"][-6:]
        known = behavior.evidence(state, npc)
        patterns = {p["id"]: p for p in state["behavioral_recognition"] if p["npc"] == npc}
        result[npc] = []
        for e in selected:
            item = {k: copy.deepcopy(v) for k, v in e.items() if k != "prior_evidence"}
            pattern = patterns[e["pattern"]]
            item["pattern_basis"] = copy.deepcopy(pattern)
            refs = pattern["evidence"] + e.get("assessment", {}).get("evidence", [])
            item["observed_basis"] = {r: copy.deepcopy(known[r]) for r in refs}
            result[npc].append(item)
    return result
