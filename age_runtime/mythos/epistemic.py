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
    if not isinstance(request, dict) or set(request) != {"npc", "speaker", "claim", "stance", "intent"}:
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
    # Exact duplicates within one engine turn add no new continuity.
    if any(all(e[k] == v for k, v in entry.items() if k != "id") for e in ledger):
        raise ValueError("duplicate dialogue claim")
    ledger.append(entry)

def public_projection(state):
    """Only what was actually communicated; no truth or intent annotation."""
    return [{k: v for k, v in e.items() if k not in ("speaker_stance", "speaker_intent")}
            for e in state.get("dialogue", [])]

def referee_projection(state, participants):
    """Return relevant private records, with stable references to prior claims."""
    return copy.deepcopy([e for e in state.get("dialogue", [])
                         if e["speaker"] in participants or e["listener"] in participants])
