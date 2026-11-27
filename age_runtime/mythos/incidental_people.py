"""Selective incidental people: identity continuity without invented native stats."""
import copy
import re


def record(state, rules, request, npc_available, text):
    if not rules.get("incidental_people") or not isinstance(request, dict):
        raise ValueError("incidental people unavailable")
    kind = request.get("kind")
    ledger = state["incidental_people"]
    identity = request.get("id")
    if not isinstance(identity, str) or not re.fullmatch(r"person:[a-z][a-z0-9_]{0,63}", identity):
        raise ValueError("invalid incidental identity")
    if kind == "introduce":
        if set(request) != {"kind", "id", "description", "basis"}:
            raise ValueError("invalid incidental introduction")
        if identity in ledger or len(ledger) >= 64:
            raise ValueError("identity already established or limit reached")
        description = text(request["description"], 160)
        basis = text(request["basis"], 240)
        ledger[identity] = {"id": identity, "description": description,
                            "name": None, "role": None, "tier": "incidental",
                            "first_seen": state["time"], "last_seen": state["time"],
                            "location": state["location"], "encounters": 1,
                            "basis": basis, "history": []}
        return
    if identity not in ledger:
        raise ValueError("unknown incidental identity")
    person = ledger[identity]
    if len(person["history"]) >= 32:
        raise ValueError("incidental history limit")
    if kind == "recognize":
        if set(request) != {"kind", "id", "basis"}:
            raise ValueError("invalid recognition")
        # Pilot deliberately supports repeat encounters at the established
        # node only. Elsewhere requires future reviewed movement authority.
        if person["location"] != state["location"] or person["last_seen"] == state["time"]:
            raise ValueError("recognition requires distinct local encounter")
        basis = text(request["basis"], 240)
        person["last_seen"] = state["time"]
        person["encounters"] += 1
    elif kind == "promote":
        if set(request) != {"kind", "id", "name", "role", "basis"} or person["tier"] != "incidental":
            raise ValueError("invalid incidental promotion")
        if person["location"] != state["location"] or person["last_seen"] != state["time"]:
            raise ValueError("promotion requires current encounter")
        name, role = text(request["name"], 80), text(request["role"], 120)
        names = {n["name"].casefold() for n in state["npcs"].values()}
        names.update(p["name"].casefold() for p in ledger.values() if p["name"])
        if name.casefold() in names:
            raise ValueError("identity name collision")
        basis = text(request["basis"], 240)
        person.update(name=name, role=role, tier="supporting")
    else:
        raise ValueError("invalid incidental operation")
    person["history"].append({"kind": kind, "at": state["time"],
                              "location": state["location"], "basis": basis})


def projection(state, *, referee=False):
    people = copy.deepcopy(list(state.get("incidental_people", {}).values()))
    if referee:
        return people
    # Last observed whereabouts, never a claim of current presence.
    return [{k: v for k, v in p.items() if k not in ("basis", "history")} for p in people]
