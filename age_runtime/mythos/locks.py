"""Local, permission-backed opportunities; never bypass authored actions."""
import copy
import re
from age_runtime.mythos import agreements, object_actions

def record(state, rules, request, npc_available, local_entities, text):
    if not rules.get("narrative_locks"):
        raise ValueError("narrative locks unavailable")
    if not isinstance(request, dict) or set(request) != {"id", "permission", "object", "basis"}:
        raise ValueError("invalid lock fields")
    lid, aid, oid = request["id"], request["permission"], request["object"]
    if not isinstance(lid, str) or not re.fullmatch(r"lock:[a-z][a-z0-9_]{0,63}", lid):
        raise ValueError("invalid lock identity")
    if not isinstance(aid, str) or not isinstance(oid, str):
        raise ValueError("invalid lock references")
    locks = state["narrative_locks"]
    if len(locks) >= 64 or any(x["id"] == lid or x["object"] == oid for x in locks):
        raise ValueError("duplicate lock or record limit")
    a = agreements.project(state).get(aid)
    entity = local_entities(state).get(oid)
    if (not a or a["kind"] != "permission" or a["status"] != "active"
            or a["issuer"] != a["npc"] or a["condition"] is not None
            or a["location"] != state["location"] or a["turn"] != state["turn"]
            or not entity or entity["kind"] != "object" or not object_actions.usable(entity) or entity.get("custodian") != a["npc"]
            or not npc_available(state, rules, {"npc": a["npc"], "location": state["location"]})):
        raise ValueError("lock requires current unconditional permission from local custodian")
    locks.append({"id": lid, "permission": aid, "object": oid, "npc": a["npc"],
                  "location": state["location"], "basis": text(request["basis"], 240),
                  "turn": state["turn"], "at": state["time"]})

def available(state, rules, lock, npc_available, local_entities):
    a = agreements.project(state).get(lock["permission"])
    e = local_entities(state).get(lock["object"])
    return bool(a and a["status"] == "active" and e and object_actions.usable(e)
                and e.get("custodian") == lock["npc"]
                and state["location"] == lock["location"]
                and state["npcs"][lock["npc"]]["location"] == state["location"]
                and npc_available(state, rules, {"npc": lock["npc"], "location": state["location"]}))

def actions(state, rules, npc_available, local_entities):
    if not rules.get("narrative_locks"):
        return []
    return [{"id": "examine:" + lock["id"], "label": "Examine " + local_entities(state)[lock["object"]]["label"],
             "location": state["location"], "minutes": 10, "interval_seconds": 600,
             "activity": "active", "narrative_lock": lock["id"],
             "test": {"attribute": "INT", "skill": "Investigate", "tn": 7,
                      "significance": "minor", "decision": False}}
            for lock in state.get("narrative_locks", [])
            if "examine:" + lock["id"] not in state["used"]
            and available(state, rules, lock, npc_available, local_entities)]

def action_available(state, rules, action, npc_available, local_entities):
    if "narrative_lock" not in action:
        return True
    lock = next((x for x in state["narrative_locks"] if x["id"] == action["narrative_lock"]), None)
    return bool(lock and available(state, rules, lock, npc_available, local_entities))

def projection(state, rules, npc_available, local_entities):
    return [{**copy.deepcopy(lock),
             "status": "spent" if "examine:" + lock["id"] in state["used"] else
             "ready" if available(state, rules, lock, npc_available, local_entities) else "blocked"}
            for lock in state.get("narrative_locks", [])]
