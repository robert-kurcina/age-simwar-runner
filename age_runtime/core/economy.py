"""Bounded SH44SER Economy Design projects: native Shortfall, simple delay policy.

Capacity is scenario-rated, not derived from GDP. Each economy turn selects
one to three axes, with authored order breaking ties. No character tests.
"""
AXES = {"industrial", "energy", "labor", "robot_labor", "logistics", "shipping",
        "materials", "finance", "legal_permission", "political_capacity",
        "security", "environmental_tolerance"}

def bottleneck(need, capacities):
    if type(need) is not int or not 1 <= need <= 5:
        raise ValueError("project need must be 1–5")
    if not isinstance(capacities, list) or not 1 <= len(capacities) <= 3:
        raise ValueError("select one to three capacity axes")
    seen = set()
    for axis, rating in capacities:
        if not isinstance(axis, str) or axis not in AXES or axis in seen:
            raise ValueError("invalid or duplicate capacity axis")
        if type(rating) is not int or not 0 <= rating <= 5:
            raise ValueError("capacity rating must be 0–5")
        seen.add(axis)
    axis, rating = min(capacities, key=lambda pair: pair[1])
    shortfall = need - rating
    return {"axis": axis if shortfall > 0 else None, "shortfall": shortfall,
            "outcome": ("clear" if shortfall <= 0 else "minor_delay" if shortfall == 1
                        else "serious_delay" if shortfall == 2 else "stalled" if shortfall == 3
                        else "scope_not_credible")}

def validate_projects(s):
    if "economy_projects" not in s:
        if "project_dependencies" in s:
            raise ValueError("dependencies require economy projects")
        return
    projects = s["economy_projects"]
    if not isinstance(projects, list) or not projects:
        raise ValueError("economy_projects must be a nonempty list")
    # This is a separate opt-in civilian project slice. Existing special
    # fulfillment rules have their own invariants and are not mixed yet.
    if any(s.get(k) for k in ("service_restoration", "community_assistance", "civic_agreement")):
        raise ValueError("mixed economy and civic fulfillment not supported")
    ids, owned, inputs = set(), set(), set()
    for p in projects:
        if not isinstance(p, dict) or set(p) != {"id", "participant", "need", "axes", "stages",
                                                "progress", "delay", "complications"}:
            raise ValueError("invalid economy project fields")
        if not isinstance(p["id"], str) or not p["id"].strip() or p["id"] in ids:
            raise ValueError("invalid or duplicate project ID")
        ids.add(p["id"])
        actor = s.get("actors", {}).get(p["participant"]) if isinstance(p["participant"], str) else None
        if actor is None:
            raise ValueError("unknown project participant")
        if type(p["stages"]) is not int or p["stages"] < 1:
            raise ValueError("project must have positive stage count")
        keys = [p[k] for k in ("progress", "delay", "complications")]
        if any(not isinstance(k, str) or k not in s["initial"] for k in keys):
            raise ValueError("unknown project counter")
        if len(set(keys)) != 3 or owned.intersection(keys):
            raise ValueError("project counters must be distinct")
        owned.update(keys)
        if any(s["initial"][k] < 0 for k in keys) or s["initial"][p["progress"]] > p["stages"]:
            raise ValueError("invalid initial project counters")
        axes = p["axes"]
        if not isinstance(axes, list) or not 1 <= len(axes) <= 3:
            raise ValueError("select one to three capacity axes")
        ratings = []
        for pair in axes:
            if not isinstance(pair, dict) or set(pair) != {"axis", "key"}:
                raise ValueError("invalid capacity binding")
            key = pair["key"]
            if not isinstance(key, str) or key not in s["initial"]:
                raise ValueError("unknown capacity property")
            inputs.add(key)
            ratings.append((pair["axis"], s["initial"][key]))
            keys.append(key)
        bottleneck(p["need"], ratings)
        if any(k not in actor.get("visible_keys", []) or actor.get("report_delay_minutes", {}).get(k, 0) for k in keys):
            raise ValueError("project properties must be currently observable")
    validate_dependencies(s)
    if owned.intersection(inputs):
        raise ValueError("project counters cannot also be capacity inputs")
    # For this bounded slice, capacity updates are unconditional dated
    # events only, checked over the entire timeline before play.
    touched = {e["key"] for e in s["events"]}
    dependent = {k for e in s.get("dependent_events", []) for k in e["updates"]}
    if owned.intersection(touched | dependent) or inputs.intersection(dependent):
        raise ValueError("external event may not write project counters or conditional capacity")
    values = {k: s["initial"][k] for k in inputs}
    for e in sorted(s["events"], key=lambda e: e["minute"]):
        if e["key"] in values:
            values[e["key"]] += e["delta"]
            if not 0 <= values[e["key"]] <= 5:
                raise ValueError("scheduled capacity outside 0–5")


def validate_dependencies(s):
    """Opt-in milestone gates. Both sponsors must know the reported prerequisite."""
    if "project_dependencies" not in s:
        return
    rules = s["project_dependencies"]
    projects = {p["id"]: p for p in s["economy_projects"]}
    if not isinstance(rules, dict) or not rules:
        raise ValueError("invalid project dependencies")
    for pid, dependencies in rules.items():
        if pid not in projects or not isinstance(dependencies, list) or not dependencies:
            raise ValueError("unknown dependent project or empty prerequisites")
        sponsor = s["actors"][projects[pid]["participant"]]
        seen = set()
        for rule in dependencies:
            if (not isinstance(rule, dict) or set(rule) != {"project", "minimum_stage"}
                    or not isinstance(rule["project"], str) or rule["project"] not in projects
                    or rule["project"] == pid or rule["project"] in seen):
                raise ValueError("invalid project prerequisite")
            predecessor = projects[rule["project"]]
            if (predecessor["participant"] == projects[pid]["participant"]
                    or type(rule["minimum_stage"]) is not int
                    or not 1 <= rule["minimum_stage"] <= predecessor["stages"]):
                raise ValueError("dependency requires a cross-faction milestone")
            key = predecessor["progress"]
            if key not in sponsor.get("visible_keys", []) or sponsor.get("report_delay_minutes", {}).get(key, 0):
                raise ValueError("dependency milestone must be currently observable")
            seen.add(rule["project"])
    # Reject cycles rather than silently creating deadlocked industrial programs.
    pending = set(projects)
    while pending:
        ready = {pid for pid in pending if not any(r["project"] in pending for r in rules.get(pid, []))}
        if not ready:
            raise ValueError("cyclic project dependencies")
        pending -= ready


def dependency_status(s, pid, values):
    projects = {p["id"]: p for p in s.get("economy_projects", [])}
    return [{"project": rule["project"], "minimum_stage": rule["minimum_stage"],
             "observed_stage": values[projects[rule["project"]]["progress"]],
             "met": values[projects[rule["project"]]["progress"]] >= rule["minimum_stage"]}
            for rule in s.get("project_dependencies", {}).get(pid, [])]


def resolve_projects(s, state, minute):
    # Snapshot before any project advances: no list-order benefit or same-turn cascade.
    opening_values = dict(state["values"]) if s.get("project_dependencies") else {}
    for p in s.get("economy_projects", []):
        v = state["values"]
        if v[p["progress"]] >= p["stages"]:
            continue
        result = bottleneck(p["need"], [(a["axis"], v[a["key"]]) for a in p["axes"]])
        dependencies = dependency_status(s, p["id"], opening_values)
        if dependencies and not all(r["met"] for r in dependencies):
            result = {**result, "outcome": "dependency_blocked"}
        if dependencies:
            result["dependencies"] = dependencies
        outcome = result["outcome"]
        # A delay is one lost project turn, not an additional global clock
        # advance. Persistent shortfall is re-evaluated next turn.
        updates = ({p["progress"]: 1} if outcome == "clear" else
                   {p["delay"]: 1} if outcome in ("minor_delay", "dependency_blocked") else
                   {p["delay"]: 1, p["complications"]: 1} if outcome == "serious_delay" else {})
        for key, delta in updates.items():
            v[key] += delta
            state["ledger"].append({"id": "economy:" + p["id"] + ":" + str(minute) + ":" + key,
                                    "minute": minute, "key": key, "delta": delta, "value": v[key]})
        state["project_results"].append({"id": p["id"], "participant": p["participant"],
                                         "minute": minute, **result})


def validate_capacity_actions(s):
    """Explicit, funded capacity improvements; no model-authored deltas."""
    actions = s.get("capacity_actions")
    if actions is None and "capacity_actions" not in s:
        return
    if not isinstance(actions, dict) or not actions or not s.get("economy_projects"):
        raise ValueError("capacity actions require economy projects")
    projects = {p["id"]: p for p in s["economy_projects"]}
    inputs = {a["key"] for p in projects.values() for a in p["axes"]}
    counters = {p[k] for p in projects.values() for k in ("progress", "delay", "complications")}
    external = {e["key"] for e in s["events"]} | {
        k for e in s.get("dependent_events", []) for k in e["updates"]}
    for name, a in actions.items():
        if name not in s.get("action_catalog", {}) or not isinstance(a, dict) or set(a) != {
                "project", "capacity", "resource", "cost"}:
            raise ValueError("invalid capacity action")
        if not all(isinstance(a[k], str) for k in ("project", "capacity", "resource")):
            raise ValueError("invalid capacity action binding")
        p = projects.get(a["project"])
        if p is None or a["capacity"] not in {x["key"] for x in p["axes"]}:
            raise ValueError("unknown project capacity")
        actor_id = p["participant"]
        if s["action_catalog"][name]["actors"] != [actor_id]:
            raise ValueError("capacity action must belong to project sponsor")
        # Shared ratings could silently benefit another sponsor; defer that
        # mechanic until a scenario explicitly needs joint investment.
        if any(other["id"] != p["id"] and a["capacity"] in
               {x["key"] for x in other["axes"]} for other in projects.values()):
            raise ValueError("capacity action requires project-local rating")
        stock = a["resource"]
        if (stock not in s["initial"] or stock in inputs | counters or
                s["initial"][stock] < 0 or {stock, a["capacity"]} & external):
            raise ValueError("capacity action requires stable resource and rating keys")
        actor = s["actors"][actor_id]
        if stock not in actor.get("visible_keys", []) or actor.get("report_delay_minutes", {}).get(stock, 0):
            raise ValueError("resource must be currently observable")
        if type(a["cost"]) is not int or a["cost"] <= 0:
            raise ValueError("capacity action cost must be positive")

def fulfill_capacity_action(s, state, record, minute):
    a = s.get("capacity_actions", {}).get(record["action"])
    if a is None:
        return
    p = next(p for p in s["economy_projects"] if p["id"] == a["project"])
    v = state["values"]
    if v[p["progress"]] >= p["stages"]:
        record["fulfillment"] = "project_complete"
    elif v[a["capacity"]] >= 5:
        record["fulfillment"] = "capacity_at_limit"
    elif v[a["resource"]] < a["cost"]:
        record["fulfillment"] = "insufficient_resources"
    else:
        for key, delta in ((a["resource"], -a["cost"]), (a["capacity"], 1)):
            v[key] += delta
            state["ledger"].append({"id": "capacity-request:" + str(record["sequence"]) + ":" + key,
                                    "minute": minute, "key": key, "delta": delta, "value": v[key]})
        record["fulfillment"] = "capacity_improved"
