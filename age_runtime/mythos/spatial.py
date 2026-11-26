"""Small, deterministic point-map resolver; no model or external dependencies."""
from datetime import datetime, timedelta
from heapq import heappop, heappush

# Difficult uses the conservative half-speed end of the DXD range.
TERRAIN_MULTIPLIER = {"Clear": 1, "Rough": 2, "Difficult": 2}

def validate(config, locations):
    nodes, zones = config["nodes"], config["zones"]
    if set(nodes) != set(locations):
        raise ValueError("point map must cover scenario locations")
    for name, zone in zones.items():
        seen = {name}
        parent = zone.get("parent")
        while parent is not None:
            if parent in seen or parent not in zones:
                raise ValueError("invalid zone ancestry")
            seen.add(parent)
            parent = zones[parent].get("parent")
    if any(n["zone"] not in zones for n in nodes.values()):
        raise ValueError("unknown node zone")
    seen = set()
    for edge in config["edges"]:
        pair = (edge["from"], edge["to"])
        if pair[0] not in nodes or pair[1] not in nodes or pair[0] == pair[1] or pair in seen:
            raise ValueError("invalid or duplicate route edge")
        seen.add(pair)
        if type(edge["minutes"]) is not int or edge["minutes"] <= 0:
            raise ValueError("invalid route time")
        if edge["terrain"] not in (*TERRAIN_MULTIPLIER, "Impassable"):
            raise ValueError("unknown terrain grade")
        if edge.get("opens") and edge.get("closes") and edge["opens"] >= edge["closes"]:
            raise ValueError("invalid route time window")

def route(config, origin, destination, at, flags):
    """Earliest feasible route without implicit waiting; stable tie-breaking.

    Only known/unlocked edges are traversed. A time window must remain open
    for the entire crossing. The small graph uses simple paths, not a
    time-dependent shortest-path assumption that would discard later arrivals.
    """
    if origin not in config["nodes"] or destination not in config["nodes"]:
        return None
    start = datetime.fromisoformat(at)
    queue = [(0, (origin,), ())]
    while queue:
        minutes, path, grades = heappop(queue)
        if path[-1] == destination:
            return {"nodes": list(path), "minutes": minutes, "terrain": list(grades)}
        for edge in config["edges"]:
            if edge["from"] != path[-1] or edge["to"] in path:
                continue
            if edge["terrain"] == "Impassable" or not all(f in flags for f in edge.get("requires_flags", [])):
                continue
            cost = edge["minutes"] * TERRAIN_MULTIPLIER[edge["terrain"]]
            departure = start + timedelta(minutes=minutes)
            arrival = departure + timedelta(minutes=cost)
            if edge.get("opens") and departure < datetime.fromisoformat(edge["opens"]):
                continue
            if edge.get("closes") and arrival > datetime.fromisoformat(edge["closes"]):
                continue
            heappush(queue, (minutes + cost, path + (edge["to"],), grades + (edge["terrain"],)))
    return None

def reachable(config, state):
    result = []
    for destination in sorted(config["nodes"]):
        if destination == state["location"]:
            continue
        trip = route(config, state["location"], destination, state["time"], state["flags"])
        if trip is not None:
            result.append({"destination": destination, **trip})
    return result
