"""Validate structured proposals without granting mutation authority.

The prototype accepts only scenario-declared administrative requests.
Registration is pure; a bounded civilian service rule may fulfill a reviewed request.
"""
def validate_catalog(s):
    catalog = s.get("action_catalog", {})
    if not isinstance(catalog, dict):
        raise ValueError("action catalog must be an object")
    for name, spec in catalog.items():
        if not isinstance(name, str) or not name or not isinstance(spec, dict):
            raise ValueError("invalid action definition")
        if set(spec) != {"description", "actors"}:
            raise ValueError("invalid action definition fields")
        if not isinstance(spec["description"], str) or not spec["description"]:
            raise ValueError("missing action description")
        ids = spec["actors"]
        if not isinstance(ids, list) or any(not isinstance(i, str) or i not in s.get("actors", {}) for i in ids):
            raise ValueError("unknown action actor")
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate action actor")

def validate_review_capacity(s):
    capacity = s.get("administrative_reviews_per_turn", 0)
    if type(capacity) is not int or capacity < 0:
        raise ValueError("invalid administrative review capacity")

def validate_service_rule(s):
    """Validate the opt-in public-service restoration fixture contract."""
    if "service_restoration" not in s:
        return
    if s["service_restoration"] is not True:
        raise ValueError("service_restoration must be true when present")
    initial = s["initial"]
    for key in ("open_service_centers", "restoration_credits"):
        if key not in initial or initial[key] < 0:
            raise ValueError("service restoration requires nonnegative " + key)
    if "restore_service_center" not in s.get("action_catalog", {}):
        raise ValueError("service restoration requires a restoration request")
    if any(e["key"] == "restoration_credits" or
           (e["key"] == "open_service_centers" and e["delta"] < 0)
           for e in s["events"]):
        raise ValueError("service restoration fixture forbids scheduled credit changes or closures")


def fulfill_service_request(s, state, record, end):
    if not s.get("service_restoration") or record["action"] != "restore_service_center":
        return
    if state["values"]["restoration_credits"] == 0:
        record["fulfillment"] = "insufficient_credits"
        return
    for key, delta in (("restoration_credits", -1), ("open_service_centers", 1)):
        state["values"][key] += delta
        state["ledger"].append({"id": "service-request:" + str(record["sequence"]) + ":" + key,
                                "minute": end, "key": key, "delta": delta,
                                "value": state["values"][key]})
    record["fulfillment"] = "restored"


def validate_civic_rules(s):
    """Validate two narrow, opt-in civilian fixture rules."""
    rules = {
        "community_assistance": (("households_assisted", "aid_packages"), ("deliver_aid",)),
        "civic_agreement": (("participating_councils", "council_a_joined", "council_b_joined"),
                            ("join_council_a", "join_council_b")),
    }
    for name, (keys, requests) in rules.items():
        if name not in s:
            continue
        if s[name] is not True:
            raise ValueError(name + " must be true when present")
        if any(k not in s["initial"] or s["initial"][k] < 0 for k in keys):
            raise ValueError(name + " requires nonnegative state variables")
        if any(r not in s.get("action_catalog", {}) for r in requests):
            raise ValueError(name + " requires its declared requests")
        if any(e["key"] in keys[1:] or (e["key"] == keys[0] and e["delta"] < 0)
               for e in s["events"]):
            raise ValueError(name + " forbids scheduled resource or consent changes")
        if name == "civic_agreement":
            for key, action in zip(keys[1:], requests):
                if s["initial"][key] not in (0, 1):
                    raise ValueError("consent must be binary")
                if s["action_catalog"][action]["actors"] != [key.removesuffix("_joined")]:
                    raise ValueError("each council must control its own consent")


def commit_civic_delta(state, record, end, key, delta):
    state["values"][key] += delta
    state["ledger"].append({"id": "civic-request:" + str(record["sequence"]) + ":" + key,
                            "minute": end, "key": key, "delta": delta,
                            "value": state["values"][key]})


def fulfill_civic_request(s, state, record, end):
    action = record["action"]
    if s.get("community_assistance") and action == "deliver_aid":
        if state["values"]["aid_packages"] == 0:
            record["fulfillment"] = "insufficient_packages"
            return
        commit_civic_delta(state, record, end, "aid_packages", -1)
        commit_civic_delta(state, record, end, "households_assisted", 10)
        record["fulfillment"] = "delivered"
    if s.get("civic_agreement") and action in ("join_council_a", "join_council_b"):
        key = action.removeprefix("join_") + "_joined"
        if state["values"][key]:
            record["fulfillment"] = "already_joined"
            return
        commit_civic_delta(state, record, end, key, 1)
        commit_civic_delta(state, record, end, "participating_councils", 1)
        record["fulfillment"] = "joined"


def resolve_reviews(s, state, end):
    """Review pending administrative requests FIFO within a fixed capacity.

    Review alone does not imply fulfillment; the opt-in service rule records
    fulfillment separately and accounts for its finite credits.
    """
    capacity = s.get("administrative_reviews_per_turn", 0)
    for record in state["requests"]:
        if capacity == 0:
            break
        if record["status"] == "validated_request":
            record["status"] = "reviewed"
            record["reviewed_minute"] = end
            fulfill_service_request(s, state, record, end)
            fulfill_civic_request(s, state, record, end)
            capacity -= 1

def available_requests(s, actor_id):
    if actor_id not in s.get("actors", {}):
        raise ValueError("unknown actor")
    return {name: {"description": spec["description"]}
            for name, spec in s.get("action_catalog", {}).items()
            if actor_id in spec["actors"]}

def validate_request(s, actor_id, proposal):
    """Trusted caller supplies actor identity; proposal cannot override it."""
    if not isinstance(proposal, dict) or set(proposal) != {"action"}:
        raise ValueError("proposal must contain only action")
    name = proposal["action"]
    if not isinstance(name, str) or name not in available_requests(s, actor_id):
        raise ValueError("action unavailable")
    return {"actor": actor_id, "action": name, "status": "validated_request"}

def register_request(s, state, actor_id, proposal):
    """Return a detached record; does not mutate state or imply execution."""
    if state["minute"] >= s["end_minute"]:
        raise ValueError("session ended")
    record = validate_request(s, actor_id, proposal)
    return {**record, "turn": state["turn"], "minute": state["minute"]}
