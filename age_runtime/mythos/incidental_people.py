"""Selective incidental people: identity continuity without invented native stats."""
import copy
import re
from datetime import datetime
from age_runtime.mythos import spatial


def validate(rules):
    allowed = rules.get("incidental_public_locations", [])
    if not isinstance(allowed, list) or any(not isinstance(x, str) for x in allowed) or len(set(allowed)) != len(allowed):
        raise ValueError("invalid incidental public locations")
    if allowed and (not rules.get("incidental_people") or set(allowed) - set(rules.get("spatial", {}).get("nodes", {}))):
        raise ValueError("incidental movement requires reviewed public nodes")


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
        if person["last_seen"] == state["time"]:
            raise ValueError("recognition requires distinct local encounter")
        if person["location"] != state["location"]:
            # A last sighting is not a current anchor. Only ordinary, reviewed
            # public routes and elapsed time justify cross-node recognition.
            # Explicitly opt in; no inference of access to restricted sites.
            allowed = rules.get("incidental_public_locations", [])
            if person["location"] not in allowed or state["location"] not in allowed:
                raise ValueError("recognition outside reviewed public locations")
            config = dict(rules["spatial"], edges=[e for e in rules["spatial"]["edges"]
                          if e["from"] in allowed and e["to"] in allowed
                          and not e.get("requires_flags") and not e.get("opens") and not e.get("closes")])
            route = spatial.route(config, person["location"], state["location"], person["last_seen"], [])
            elapsed = (datetime.fromisoformat(state["time"]) - datetime.fromisoformat(person["last_seen"])).total_seconds()
            if not route or route["seconds"] > elapsed:
                raise ValueError("insufficient elapsed time for recognition")
        basis = text(request["basis"], 240)
        person["last_seen"] = state["time"]
        person["location"] = state["location"]
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
