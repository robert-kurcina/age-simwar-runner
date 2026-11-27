"""Replayable runtime negotiations; only reviewed transfer terms are permitted."""
from copy import deepcopy
from age_runtime.core.actions import settle_terms, stock_owners


def validate(s):
    if "dynamic_negotiation" in s and (s["dynamic_negotiation"] is not True
                                      or not s.get("resource_transfers")):
        raise ValueError("dynamic negotiation requires reviewed transfers")


def options(s, state, actor):
    if not s.get("dynamic_negotiation"):
        return {}
    owners = stock_owners(s)
    pairs = {}
    for name, t in s["resource_transfers"].items():
        parties = {owners[t["source"]], owners[t["destination"]]}
        if actor in parties:
            other = next(iter(parties - {actor}))
            pairs.setdefault(other, {})[name] = deepcopy(t)
    return pairs


def view(s, state, actor):
    if not s.get("dynamic_negotiation"):
        return {}
    return {"negotiation": {"counterpart_terms": options(s, state, actor),
            "proposals": [deepcopy(p) for p in state["negotiations"].values()
                          if actor in (p["proposer"], p["recipient"])],
            "last_due_minute": s["end_minute"] // s["turn_minutes"] * s["turn_minutes"]}}


def apply(s, state, actor, command):
    """Trusted actor identity; proposal or response immediately records consent."""
    if not s.get("dynamic_negotiation") or actor not in s["actors"] or state["minute"] >= s["end_minute"]:
        raise ValueError("negotiation unavailable")
    if not isinstance(command, dict):
        raise ValueError("invalid negotiation command")
    kind = command.get("kind")
    if kind in ("propose", "counter"):
        fields = {"kind", "id", "recipient", "transfers", "due_minute"}
        if kind == "counter":
            fields.add("parent")
        if set(command) != fields:
            raise ValueError("invalid proposal fields")
        pid, recipient, terms, due = (command[k] for k in ("id", "recipient", "transfers", "due_minute"))
        if (not isinstance(pid, str) or not pid.strip() or len(pid) > 128
                or pid in state["negotiations"] or pid in s.get("agreements", {})
                or not isinstance(recipient, str) or recipient == actor
                or not isinstance(terms, list) or not terms
                or any(not isinstance(t, str) for t in terms)
                or len(set(terms)) != len(terms)
                or type(due) is not int or not state["minute"] < due <= s["end_minute"]
                or due % s["turn_minutes"]):
            raise ValueError("invalid proposal identity or terms")
        permitted = options(s, state, actor).get(recipient, {})
        if any(t not in permitted for t in terms):
            raise ValueError("terms must involve only the two parties")
        if kind == "counter":
            parent = pending(state, command["parent"], actor)
            if recipient != parent["proposer"]:
                raise ValueError("counter must address original proposer")
            parent["status"] = "countered"
        state["negotiations"][pid] = {"id": pid, "proposer": actor, "recipient": recipient,
            "transfers": list(terms), "due_minute": due, "status": "proposed",
            **({"parent": command["parent"]} if kind == "counter" else {})}
    elif kind in ("accept", "reject"):
        if set(command) != {"kind", "id"}:
            raise ValueError("invalid response fields")
        p = pending(state, command["id"], actor)
        p["status"] = "committed" if kind == "accept" else "rejected"
    else:
        raise ValueError("unknown negotiation command")


def pending(state, pid, actor):
    p = state["negotiations"].get(pid) if isinstance(pid, str) else None
    if (p is None or p["recipient"] != actor or p["status"] != "proposed"
            or p["due_minute"] <= state["minute"]):
        raise ValueError("proposal unavailable for response")
    return p


def resolve(s, state, minute):
    for pid, p in sorted(state.get("negotiations", {}).items()):
        if p["due_minute"] != minute:
            continue
        if p["status"] == "proposed":
            p["status"] = "expired"
        elif p["status"] == "committed":
            outcome = {}
            settle_terms(s, state, minute, pid, p["transfers"], outcome)
            p["status"] = outcome["status"]
