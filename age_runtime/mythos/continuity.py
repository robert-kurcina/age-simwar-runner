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
            if not set(cfg["flags"]) & set(actions[carrier["action"]].get("grant", [])):
                raise ValueError("carrier does not establish function")

def blocked(state, cfg):
    return any(f in state["flags"] for f in cfg.get("unavailable_flags", []))

def projection(state, rules, legal):
    """GM-only: distinguish established information, ready routes, and blocked routes.
    
    A route not immediately legal is not necessarily permanently lost.
    """
    choices = {a["id"] for a in legal}
    result = []
    for key, cfg in rules.get("narrative_functions", {}).items():
        established = any(f in state["flags"] for f in cfg["flags"])
        carriers = []
        for c in cfg["carriers"]:
            action = next(a for a in rules["actions"] if a["id"] == c["action"])
            unavailable = (action.get("npc") is not None and blocked(state, rules["npcs"][action["npc"]]))
            spent = action["id"] in state["used"] and not action.get("repeatable")
            status = "blocked" if unavailable else "spent" if spent else "ready" if action["id"] in choices else "conditional"
            carriers.append({"action": action["id"], "kind": c["kind"], "status": status})
        result.append({"id": key, "purpose": cfg["purpose"], "established": established,
                       "carriers": carriers, "no_immediate_route": not established and not any(c["status"] == "ready" for c in carriers)})
    return result
