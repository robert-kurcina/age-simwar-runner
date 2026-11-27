"""Actor-scoped observations of committed incidental object outcomes."""
import copy
import re

def record(state, rules, request, npc_available, local_entities, text):
    if not rules.get("action_observations") or not isinstance(request, dict) or set(request) != {"id", "npc", "action", "kind", "basis"}:
        raise ValueError("invalid action observation")
    oid, npc, aid, kind = (request[k] for k in ("id", "npc", "action", "kind"))
    if not isinstance(oid, str) or not re.fullmatch(r"obs:[a-z][a-z0-9_]{0,63}", oid):
        raise ValueError("invalid observation identity")
    if not isinstance(npc, str) or npc not in state["npcs"] or state["npcs"][npc]["location"] != state["location"] or not npc_available(state, rules, {"npc": npc, "location": state["location"]}):
        raise ValueError("observation requires available local NPC")
    if kind not in ("witnessed", "discovered"):
        raise ValueError("invalid observation kind")
    action = next((a for a in state["object_actions"] if a["id"] == aid), None)
    if not action:
        raise ValueError("unknown committed action")
    ledger = state["action_observations"]
    if len(ledger) >= 256 or any(e["id"] == oid or (e["npc"], e["action"]) == (npc, aid) for e in ledger):
        raise ValueError("duplicate observation or record limit")
    obj = local_entities(state).get(action["object"])
    if (not obj or obj.get("lifecycle") != action["outcome"]
            or ("function_after" in action and obj.get("function") != action["function_after"])):
        raise ValueError("observed outcome no longer matches local object")
    if kind == "witnessed":
        # A witness must be registered immediately, before another action,
        # transfer, movement or dialogue changes the scene.
        if action["sequence"] != len(state["history"]) - 1 or action["at"] != state["time"] or action["location"] != state["location"]:
            # Permit consecutive witness records for the same action only.
            intervening = state["history"][action["sequence"] + 1:]
            if (action["at"] != state["time"] or action["location"] != state["location"]
                    or not intervening or any(h.get("establish", {}).get("action_observation", {}).get("action") != aid
                                              if isinstance(h, dict) else True for h in intervening)):
                raise ValueError("witness must be contemporaneous with action")
    elif obj.get("custodian") not in (None, "pc", npc):
        raise ValueError("discovery requires accessible object")
    # Store what the NPC observed, not the player's private authorization.
    ledger.append({"id": oid, "npc": npc, "action": aid, "object": action["object"],
                   "kind": kind, "outcome": action["outcome"], "condition": obj.get("properties", {}).get("condition"),
                   **({"function": obj["function"]} if "function" in obj else {}),
                   "actor": "pc" if kind == "witnessed" else None,
                   "basis": text(request["basis"], 240), "at": state["time"],
                   "turn": state["turn"], "location": state["location"]})

def projection(state, participants):
    return {npc: [copy.deepcopy({k: v for k, v in e.items() if k != "basis"})
                  for e in state.get("action_observations", []) if e["npc"] == npc][-8:]
            for npc in sorted(participants)}
