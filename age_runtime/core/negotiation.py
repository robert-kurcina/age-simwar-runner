"""Replayable negotiations with reviewed transfer and bounded permission terms."""
from copy import deepcopy
from age_runtime.core.actions import settle_terms, stock_owners


def validate(s):
    if "dynamic_negotiation" in s and (s["dynamic_negotiation"] is not True
                                      or not (s.get("resource_transfers") or s.get("permission_terms"))):
        raise ValueError("dynamic negotiation requires reviewed terms")
    if "permission_terms" not in s:
        return
    terms = s["permission_terms"]
    if not s.get("dynamic_negotiation") or not isinstance(terms, dict) or not 1 <= len(terms) <= 128:
        raise ValueError("permission terms require dynamic negotiation")
    for pid, term in terms.items():
        if (not isinstance(pid, str) or not pid.strip() or len(pid) > 80
                or not isinstance(term, dict)
                or set(term) != {"issuer", "grantee", "description", "max_due_minute"}):
            raise ValueError("invalid permission term")
        issuer, grantee = term["issuer"], term["grantee"]
        due, description = term["max_due_minute"], term["description"]
        if (not isinstance(issuer, str) or not isinstance(grantee, str)
                or issuer == grantee or issuer not in s["actors"] or grantee not in s["actors"]
                or not isinstance(description, str) or not description.strip() or len(description) > 400
                or type(due) is not int or not 0 < due <= s["end_minute"]
                or due % s["turn_minutes"]):
            raise ValueError("invalid permission scope or authority")


def options(s, state, actor):
    if not s.get("dynamic_negotiation"):
        return {}
    owners = stock_owners(s)
    pairs = {}
    for name, t in s.get("resource_transfers", {}).items():
        parties = {owners[t["source"]], owners[t["destination"]]}
        if actor in parties:
            other = next(iter(parties - {actor}))
            pairs.setdefault(other, {})[name] = deepcopy(t)
    return pairs


def permission_options(s, actor):
    return {name: deepcopy(term) for name, term in s.get("permission_terms", {}).items()
            if actor in (term["issuer"], term["grantee"])}


def active_permission(s, state, permission_id, issuer, grantee):
    """Check an exact authored permission term; no access/evidence is granted here."""
    term = s.get("permission_terms", {}).get(permission_id)
    return bool(term and (term["issuer"], term["grantee"]) == (issuer, grantee)
                and any(p.get("permission") == permission_id and p["status"] == "active"
                        and state["minute"] < p["due_minute"]
                        for p in state.get("negotiations", {}).values()))


def view(s, state, actor):
    if not s.get("dynamic_negotiation"):
        return {}
    return {"negotiation": {"counterpart_terms": options(s, state, actor),
            **({"permission_terms": permission_options(s, actor)} if "permission_terms" in s else {}),
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
        is_permission = "permission" in command
        term_field = "permission" if is_permission else "transfers"
        fields = {"kind", "id", "recipient", term_field, "due_minute"}
        if kind == "counter":
            fields.add("parent")
        if set(command) != fields:
            raise ValueError("invalid proposal fields")
        pid, recipient, terms, due = (command[k] for k in ("id", "recipient", term_field, "due_minute"))
        if (not isinstance(pid, str) or not pid.strip() or len(pid) > 128
                or pid in state["negotiations"] or pid in s.get("agreements", {})
                or not isinstance(recipient, str) or recipient == actor
                or type(due) is not int or not state["minute"] < due <= s["end_minute"]
                or due % s["turn_minutes"]):
            raise ValueError("invalid proposal identity or terms")
        parent = pending(state, command["parent"], actor) if kind == "counter" else None
        if parent is not None and (recipient != parent["proposer"]
                                   or ("permission" in parent) != is_permission):
            raise ValueError("counter must address original proposer and same term family")
        if is_permission:
            term = permission_options(s, actor).get(terms) if isinstance(terms, str) else None
            if (term is None or {actor, recipient} != {term["issuer"], term["grantee"]}
                    or due > term["max_due_minute"]):
                raise ValueError("permission must match reviewed parties and scope")
            if any(p.get("permission") == terms and p["status"] in ("proposed", "active")
                   and p is not parent for p in state["negotiations"].values()):
                raise ValueError("equivalent open permission")
            payload = {"permission": terms, "issuer": term["issuer"], "grantee": term["grantee"],
                       "proposed_minute": state["minute"]}
        else:
            if (not isinstance(terms, list) or not terms
                    or any(not isinstance(t, str) for t in terms) or len(set(terms)) != len(terms)):
                raise ValueError("invalid transfer terms")
            permitted = options(s, state, actor).get(recipient, {})
            if any(t not in permitted for t in terms):
                raise ValueError("terms must involve only the two parties")
            payload = {"transfers": list(terms)}
        if parent is not None:
            parent["status"] = "countered"
            if is_permission:
                parent["resolved_minute"] = state["minute"]
        state["negotiations"][pid] = {"id": pid, "proposer": actor, "recipient": recipient,
            **payload, "due_minute": due, "status": "proposed",
            **({"parent": command["parent"]} if kind == "counter" else {})}
    elif kind in ("accept", "reject"):
        if set(command) != {"kind", "id"}:
            raise ValueError("invalid response fields")
        p = pending(state, command["id"], actor)
        if "permission" in p:
            p["status"] = "active" if kind == "accept" else "rejected"
            p["accepted_minute" if kind == "accept" else "resolved_minute"] = state["minute"]
        else:
            p["status"] = "committed" if kind == "accept" else "rejected"
    elif kind in ("withdraw", "revoke", "release"):
        if set(command) != {"kind", "id"}:
            raise ValueError("invalid permission response fields")
        pid = command["id"]
        p = state["negotiations"].get(pid) if isinstance(pid, str) else None
        if p is None or "permission" not in p or p["due_minute"] <= state["minute"]:
            raise ValueError("permission unavailable")
        required = {"withdraw": ("proposed", p["proposer"], "withdrawn"),
                    "revoke": ("active", p["issuer"], "revoked"),
                    "release": ("active", p["grantee"], "released")}
        status, owner, result = required[kind]
        if p["status"] != status or actor != owner:
            raise ValueError("permission transition not authorized")
        p["status"] = result
        p["resolved_minute"] = state["minute"]
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
        if "permission" in p:
            if p["status"] in ("proposed", "active"):
                p["status"] = "expired"
                p["resolved_minute"] = minute
        elif p["status"] == "proposed":
            p["status"] = "expired"
        elif p["status"] == "committed":
            outcome = {}
            settle_terms(s, state, minute, pid, p["transfers"], outcome)
            p["status"] = outcome["status"]
