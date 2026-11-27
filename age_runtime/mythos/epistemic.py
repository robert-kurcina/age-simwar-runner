"""Bounded epistemic dialogue records; no authority to change world truth.

An utterance is a historical claim, not proof of its content. Existing
scenario facts and mechanical effects remain authoritative. This module
deliberately does not infer truth, deception, or PC belief from prose.
"""
import copy

def _text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError("invalid dialogue text")
    return value.strip()

def record(state, rules, request, npc_available):
    if not rules.get("epistemic_dialogue") or state["ending"] or state["dxd"].get("activity", {}).get("status") == "asleep":
        raise ValueError("dialogue unavailable")
    required = {"npc", "speaker", "claim", "stance", "intent"}
    if not isinstance(request, dict) or not required <= set(request) or set(request) - required - {"proposition", "asserts", "listener_stance"}:
        raise ValueError("invalid dialogue fields")
    npc, speaker = request["npc"], request["speaker"]
    if not isinstance(npc, str) or npc not in state["npcs"] or speaker not in ("pc", npc):
        raise ValueError("invalid dialogue participants")
    if state["npcs"][npc]["location"] != state["location"] or not npc_available(state, rules, {"npc": npc, "location": state["location"]}):
        raise ValueError("dialogue participant not present")
    claim = _text(request["claim"], 400)
    stance, intent = request["stance"], request["intent"]
    if stance not in ("unstated", "believes", "doubts", "disbelieves", "unknown"):
        raise ValueError("invalid speaker stance")
    if intent not in ("unstated", "sincere", "deceive", "fabricate"):
        raise ValueError("invalid speaker intent")
    if speaker == "pc" and (stance != "unstated" or intent != "unstated"):
        raise ValueError("do not infer PC internal state")
    if intent == "sincere" and stance == "disbelieves":
        raise ValueError("contradictory speaker metadata")
    ledger = state["dialogue"]
    if len(ledger) >= 256:
        raise ValueError("dialogue record limit")
    entry = {"id": len(ledger) + 1, "turn": state["turn"], "at": state["time"],
             "location": state["location"], "speaker": speaker,
             "listener": npc if speaker == "pc" else "pc", "claim": claim,
             "speaker_stance": stance, "speaker_intent": intent}
    linked = "proposition" in request or "asserts" in request or "listener_stance" in request
    if linked:
        pid = request.get("proposition")
        asserts = request.get("asserts")
        if not isinstance(pid, str) or type(asserts) is not bool:
            raise ValueError("linked claim requires proposition and boolean assertion")
        spec = rules.get("propositions", {}).get(pid)
        if spec is None:
            raise ValueError("unknown proposition")
        # A reference may not disclose an unearned canonical fact. PC may
        # repeat a received claim even when its content is not established.
        known = sources(state, rules, speaker, pid)
        if not known:
            raise ValueError("speaker lacks proposition access")
        if speaker != "pc" and not sources(state, rules, "pc", pid):
            raise ValueError("new canonical disclosures require authored action")
        listener_stance = request.get("listener_stance", "unstated")
        if listener_stance not in ("unstated", "believes", "doubts", "disbelieves", "unknown"):
            raise ValueError("invalid listener stance")
        if speaker != "pc" and listener_stance != "unstated":
            raise ValueError("do not infer PC belief")
        entry.update(proposition=pid, asserts=asserts, listener_stance=listener_stance)
    # Exact duplicates within one engine turn add no new continuity.
    if any(all(e[k] == v for k, v in entry.items() if k != "id") for e in ledger):
        raise ValueError("duplicate dialogue claim")
    ledger.append(entry)

def public_projection(state):
    """Only what was actually communicated; no truth or intent annotation."""
    return [{k: v for k, v in e.items() if k not in ("speaker_stance", "speaker_intent", "proposition", "asserts", "listener_stance")}
            for e in state.get("dialogue", [])]

def referee_projection(state, participants):
    """Return relevant private records, with stable references to prior claims."""
    return copy.deepcopy([e for e in state.get("dialogue", [])
                         if e["speaker"] in participants or e["listener"] in participants])

def validate_propositions(rules):
    """Author registry points to existing facts, not a second world model."""
    grants = {f for a in rules["actions"] for f in a.get("grant", [])}
    for group in ("events", "encounter_table"):
        grants.update(f for a in rules.get(group, []) for f in a.get("grant", []))
    for pid, spec in rules.get("propositions", {}).items():
        _text(pid, 80)
        _text(spec["text"], 400)
        if set(spec) != {"text", "kind", "flag", "initial_knowers"}:
            raise ValueError("invalid proposition fields")
        if spec["kind"] not in ("fact", "report", "inference") or spec["flag"] not in grants:
            raise ValueError("invalid proposition basis")
        if not isinstance(spec["initial_knowers"], list) or not set(spec["initial_knowers"]) <= set(rules["npcs"]):
            raise ValueError("invalid initial knowers")

def sources(state, rules, actor, pid):
    """Access is not belief. Keep authored access and received claims distinct."""
    spec = rules["propositions"][pid]
    result = []
    if actor in spec["initial_knowers"]:
        result.append({"kind": "authored_access"})
    if actor == "pc" and spec["flag"] in state["flags"]:
        result.append({"kind": "earned", "flag": spec["flag"]})
    for e in state.get("dialogue", []):
        if e.get("proposition") == pid and e["listener"] == actor:
            result.append({"kind": "received_claim", "id": e["id"], "asserts": e["asserts"]})
    return result

def proposition_projection(state, rules, participants):
    """Private, derived on demand from flags and the existing claim ledger."""
    result = []
    for pid, spec in rules.get("propositions", {}).items():
        actors = {}
        for actor in sorted(set(participants) | {"pc"}):
            access = sources(state, rules, actor, pid)
            if not access:
                continue
            revisions = []
            for e in state.get("dialogue", []):
                if e.get("proposition") != pid:
                    continue
                if e["speaker"] == actor and e["speaker_stance"] != "unstated":
                    revisions.append({"id": e["id"], "stance": e["speaker_stance"], "asserts": e["asserts"]})
                if e["listener"] == actor and e["listener_stance"] != "unstated":
                    revisions.append({"id": e["id"], "stance": e["listener_stance"], "asserts": e["asserts"]})
            actors[actor] = {"access": access, "latest_stance": revisions[-1] if revisions else None}
        if actors:
            result.append({"id": pid, "text": spec["text"], "kind": spec["kind"],
                           "established": spec["flag"] in state["flags"], "actors": actors})
    return result
