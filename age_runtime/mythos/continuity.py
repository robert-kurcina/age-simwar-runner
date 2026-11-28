"""Small causal availability and narrative-function projection.

Flags are authoritative consequences of existing events/actions. A blocked
carrier never erases information already learned or creates new evidence.
"""
def validate(rules):
    actions = {a["id"]: a for a in rules["actions"]}
    for key, cfg in rules.get("npcs", {}).items():
        if any(not isinstance(f, str) or not f for f in cfg.get("unavailable_flags", [])):
            raise ValueError("invalid NPC availability flag")
    for key, cfg in rules.get("narrative_functions", {}).items():
        if not cfg.get("flags") or not cfg.get("carriers"):
            raise ValueError("invalid narrative function")
        for carrier in cfg["carriers"]:
            if carrier["action"] not in actions:
                raise ValueError("unknown carrier action")
            if any(npc not in rules["npcs"] or flag not in actions[carrier["action"]].get("requires_flags", []) for npc, flag in carrier.get("access_carriers", {}).items()):
                raise ValueError("invalid carrier access dependency")
            if not set(cfg["flags"]) & set(actions[carrier["action"]].get("grant", [])):
                raise ValueError("carrier does not establish function")

def blocked(state, cfg):
    return any(f in state["flags"] for f in cfg.get("unavailable_flags", []))

def projection(state, rules, legal):
    """GM-only: distinguish established information, ready routes, and blocked routes.
    
    A route not immediately legal is not necessarily permanently lost.
    """
    choices = {a["id"] for a in legal}
    actions = {a["id"]: a for a in rules["actions"]}
    result = []
    for key, cfg in rules.get("narrative_functions", {}).items():
        established = any(f in state["flags"] for f in cfg["flags"])
        carriers = []
        for c in cfg["carriers"]:
            action = actions[c["action"]]
            unavailable = (action.get("npc") is not None and blocked(state, rules["npcs"][action["npc"]]))
            unavailable = unavailable or any(blocked(state, rules["npcs"][key]) and flag not in state["flags"]
                for key, flag in c.get("access_carriers", {}).items())
            spent = action["id"] in state["used"] and not action.get("repeatable")
            expired = bool(action.get("available_until") and state["time"] >= action["available_until"])
            excluded = any(f in state["flags"] for f in action.get("excludes_flags", []))
            status = ("spent" if spent else "blocked" if unavailable or expired or excluded
                      else "ready" if action["id"] in choices else "conditional")
            carriers.append({"action": action["id"], "kind": c["kind"], "status": status})
        result.append({"id": key, "purpose": cfg["purpose"], "established": established,
                       "carriers": carriers, "no_immediate_route": not established and not any(c["status"] == "ready" for c in carriers),
                       "authored_routes_exhausted": not established and all(c["status"] in ("spent", "blocked") for c in carriers)})
    return result


def reconsideration_allowed(state, action):
    """A different request in the same group needs newly established evidence."""
    cfg = action.get("reconsideration")
    if not cfg:
        return True
    prior = next((t["refusal_context"] for t in reversed(state["dxd"]["tests"])
                  if t.get("refusal_context", {}).get("group") == cfg["group"]), None)
    if prior is None:
        return True
    return bool((set(cfg["evidence"]) & set(state["flags"])) - set(prior["evidence"]))


def record_refusal(state, action, test):
    """Snapshot all relevant evidence at refusal in the existing Test ledger."""
    cfg = action.get("reconsideration")
    if cfg:
        test["refusal_context"] = {
            "group": cfg["group"],
            "evidence": sorted(set(cfg["evidence"]) & set(state["flags"])),
        }
