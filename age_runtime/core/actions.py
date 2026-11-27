"""Validate structured proposals without granting mutation authority.

The prototype accepts only scenario-declared administrative requests.
Registration is pure; a bounded civilian service rule may fulfill a reviewed request.
"""
from age_runtime.core.economy import fulfill_capacity_action


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
    if "assistance_capacity" in s:
        cap = s["assistance_capacity"]
        if not s.get("community_assistance") or not isinstance(cap, dict) or set(cap) != {"household_limit", "households_per_package"}:
            raise ValueError("invalid assistance capacity")
        if any(type(v) is not int or v <= 0 for v in cap.values()):
            raise ValueError("assistance capacity must be positive integers")
        if s["initial"].get("households_assisted", -1) > cap["household_limit"]:
            raise ValueError("initial assistance exceeds household limit")
        if any(e["key"] == "households_assisted" for e in s["events"]):
            raise ValueError("capacity-limited assistance requires explicit requests")
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
        cap = s.get("assistance_capacity")
        amount = 10
        if cap is not None:
            amount = min(cap["households_per_package"], cap["household_limit"] - state["values"]["households_assisted"])
            if amount <= 0:
                record["fulfillment"] = "all_households_assisted"
                return
        commit_civic_delta(state, record, end, "aid_packages", -1)
        commit_civic_delta(state, record, end, "households_assisted", amount)
        record["fulfillment"] = "delivered"
    if s.get("civic_agreement") and action in ("join_council_a", "join_council_b"):
        key = action.removeprefix("join_") + "_joined"
        if state["values"][key]:
            record["fulfillment"] = "already_joined"
            return
        commit_civic_delta(state, record, end, key, 1)
        commit_civic_delta(state, record, end, "participating_councils", 1)
        record["fulfillment"] = "joined"


def stock_owners(s):
    """Single authority for economic stocks, including non-project funders."""
    projects = {p["id"]: p["participant"] for p in s.get("economy_projects", [])}
    owners = {}
    for action in s.get("capacity_actions", {}).values():
        owners.setdefault(action["resource"], set()).add(projects[action["project"]])
    reserves = s.get("funding_reserves", {})
    if "funding_reserves" in s:
        if not isinstance(reserves, dict) or not reserves or not s.get("economy_projects") or not s.get("resource_transfers"):
            raise ValueError("funding reserves require projects and reviewed transfers")
        protected = {p[k] for p in s["economy_projects"] for k in ("progress", "delay", "complications")}
        protected.update(a["key"] for p in s["economy_projects"] for a in p["axes"])
        protected.update(e["key"] for e in s["events"])
        protected.update(k for e in s.get("dependent_events", []) for k in e["updates"])
        for key, actor in reserves.items():
            if (not isinstance(key, str) or key not in s["initial"] or s["initial"][key] < 0
                    or key in owners or key in protected
                    or not isinstance(actor, str) or actor not in s["actors"]):
                raise ValueError("invalid independent funding reserve")
            profile = s["actors"][actor]
            if key not in profile.get("visible_keys", []) or profile.get("report_delay_minutes", {}).get(key, 0):
                raise ValueError("funding reserve must be currently observable by its owner")
            owners[key] = {actor}
    if any(len(ids) != 1 for ids in owners.values()):
        raise ValueError("ambiguous economic stock ownership")
    return {key: next(iter(ids)) for key, ids in owners.items()}


def validate_transfers(s):
    """Reviewed voluntary transfers between distinct civilian investment stocks."""
    owners = stock_owners(s)
    if "resource_transfers" not in s:
        return
    transfers = s["resource_transfers"]
    if not isinstance(transfers, dict) or not transfers or not s.get("economy_projects"):
        raise ValueError("resource transfers require economy projects")
    for name, t in transfers.items():
        if (not isinstance(t, dict) or set(t) != {"source", "destination", "amount"}
                or name not in s.get("action_catalog", {}) or name in s.get("capacity_actions", {})):
            raise ValueError("invalid transfer definition")
        source, destination, amount = t["source"], t["destination"], t["amount"]
        if (not isinstance(source, str) or not isinstance(destination, str)
                or source == destination or source not in owners
                or destination not in owners
                or owners[source] == owners[destination]
                or type(amount) is not int or amount <= 0):
            raise ValueError("transfer requires distinct owned stocks and positive amount")
        donor = owners[source]
        if s["action_catalog"][name]["actors"] != [donor]:
            raise ValueError("only donor may authorize transfer")


def fulfill_transfer(s, state, record, minute):
    t = s.get("resource_transfers", {}).get(record["action"])
    if t is None:
        return
    v = state["values"]
    if v[t["source"]] < t["amount"]:
        record["fulfillment"] = "insufficient_resources"
        return
    for key, delta in ((t["source"], -t["amount"]), (t["destination"], t["amount"])):
        v[key] += delta
        state["ledger"].append({"id": "transfer:" + str(record["sequence"]) + ":" + key,
                                "minute": minute, "key": key, "delta": delta, "value": v[key]})
    record["fulfillment"] = "transferred"


def agreement_actions(s):
    return {action for a in s.get("agreements", {}).values()
            for action in a["consent"].values()}


def validate_agreements(s):
    if "agreements" not in s:
        return
    agreements = s["agreements"]
    if not isinstance(agreements, dict) or not agreements:
        raise ValueError("invalid agreements")
    # Political commitments are a separate bounded slice of the existing
    # agreement resolver, not arbitrary effects or resource transfers.
    if not s.get("economy_projects"):
        validate_institutional_agreements(s)
        return
    if not s.get("resource_transfers"):
        raise ValueError("economic agreements require reviewed resource transfers")
    used = set(s.get("capacity_actions", {})) | set(s["resource_transfers"])
    for aid, a in agreements.items():
        if (not isinstance(aid, str) or not aid.strip() or not isinstance(a, dict)
                or set(a) != {"description", "consent", "transfers", "due_minute"}):
            raise ValueError("invalid agreement definition")
        if not isinstance(a["description"], str) or not a["description"].strip():
            raise ValueError("agreement description required")
        consent, transfers, due = a["consent"], a["transfers"], a["due_minute"]
        if (not isinstance(consent, dict) or len(consent) != 2
                or not isinstance(transfers, list) or not transfers
                or any(not isinstance(t, str) or t not in s["resource_transfers"] for t in transfers)
                or len(set(transfers)) != len(transfers)
                or type(due) is not int or not 0 < due <= s["end_minute"]
                or due % s["turn_minutes"]):
            raise ValueError("invalid agreement terms")
        for actor, action in consent.items():
            if (actor not in s["actors"] or not isinstance(action, str) or action in used
                    or s["action_catalog"].get(action, {}).get("actors") != [actor]):
                raise ValueError("agreement consent must be independently authorized")
            used.add(action)
        owners = stock_owners(s)
        for name in transfers:
            t = s["resource_transfers"][name]
            if {owners[t["source"]], owners[t["destination"]]} != set(consent):
                raise ValueError("agreement transfer must involve its two parties")


def validate_institutional_agreements(s):
    agreements = s["agreements"]
    if any(k in s for k in ("economy_projects", "capacity_actions", "resource_transfers",
                            "dynamic_negotiation", "service_restoration", "community_assistance",
                            "civic_agreement", "assistance_capacity", "dependent_events", "funding_reserves")):
        raise ValueError("institutional agreements cannot mix fulfillment mechanisms")
    if s["events"] or s["constraints"]:
        raise ValueError("institutional agreements require explicit consent outcomes")
    used, outputs = set(), {}
    for aid, a in agreements.items():
        if (not isinstance(aid, str) or not aid.strip() or not isinstance(a, dict)
                or set(a) != {"description", "consent", "due_minute", "outcome", "requires"}):
            raise ValueError("invalid institutional agreement fields")
        consent, due, key = a["consent"], a["due_minute"], a["outcome"]
        if (not isinstance(a["description"], str) or not a["description"].strip()
                or not isinstance(consent, dict) or len(consent) < 2
                or type(due) is not int or not 0 < due <= s["end_minute"]
                or due % s["turn_minutes"] or not isinstance(key, str)
                or s["initial"].get(key) != 0 or key in outputs
                or not isinstance(a["requires"], list)
                or any(not isinstance(x, str) for x in a["requires"])
                or len(set(a["requires"])) != len(a["requires"])):
            raise ValueError("invalid institutional agreement terms")
        outputs[key] = aid
        for actor, action in consent.items():
            if (actor not in s["actors"] or not isinstance(action, str) or action in used
                    or s["action_catalog"].get(action, {}).get("actors") != [actor]):
                raise ValueError("institutional consent must be independently authorized")
            used.add(action)
            profile = s["actors"][actor]
            if key not in profile.get("visible_keys", []) or profile.get("report_delay_minutes", {}).get(key, 0):
                raise ValueError("signatories require current outcome visibility")
    if used != set(s.get("action_catalog", {})) or set(outputs) != set(s["initial"]):
        raise ValueError("institutional slice accepts only declared consent and outcome flags")
    for aid, a in agreements.items():
        for prerequisite in a["requires"]:
            if (prerequisite not in agreements
                    or agreements[prerequisite]["due_minute"] >= a["due_minute"]
                    or not set(a["consent"]) <= set(agreements[prerequisite]["consent"])):
                raise ValueError("prerequisite must be earlier and visible to all dependent signatories")


def resolve_agreements(s, state, minute):
    """One-shot, all-or-nothing settlement of reviewed mutual consent.

    Ordinary orders resolve first. No balance reservation or forced debt.
    A shortfall is a recorded default, never an invented negative balance.
    """
    for aid, a in s.get("agreements", {}).items():
        if minute != a["due_minute"]:
            continue
        signed = sorted(actor for actor, action in a["consent"].items()
                        if any(r["actor"] == actor and r["action"] == action
                               and r["status"] == "reviewed"
                               for r in state["requests"]))
        outcome = {"id": aid, "minute": minute, "consenting": signed, "status": "not_agreed"}
        if len(signed) == len(a["consent"]):
            if "outcome" in a:
                if all(state["values"][s["agreements"][p]["outcome"]] == 1 for p in a["requires"]):
                    key = a["outcome"]
                    state["values"][key] = 1
                    state["ledger"].append({"id": "agreement:" + aid + ":" + key,
                        "minute": minute, "key": key, "delta": 1, "value": 1})
                    outcome["status"] = "fulfilled"
                else:
                    outcome["status"] = "prerequisite_unmet"
            else:
                settle_terms(s, state, minute, aid, a["transfers"], outcome)
        state["agreement_results"].append(outcome)


def settle_terms(s, state, minute, aid, transfers, outcome):
    debits, changes = {}, {}
    for name in transfers:
        t = s["resource_transfers"][name]
        source, destination, amount = t["source"], t["destination"], t["amount"]
        debits[source] = debits.get(source, 0) + amount
        changes[source] = changes.get(source, 0) - amount
        changes[destination] = changes.get(destination, 0) + amount
    if any(state["values"][k] < n for k, n in debits.items()):
        outcome["status"] = "defaulted"
    else:
        for key, delta in sorted(changes.items()):
            if not delta:
                continue
            state["values"][key] += delta
            state["ledger"].append({"id": "agreement:" + aid + ":" + key,
                "minute": minute, "key": key, "delta": delta, "value": state["values"][key]})
        outcome["status"] = "fulfilled"


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
            fulfill_capacity_action(s, state, record, end)
            fulfill_transfer(s, state, record, end)
            if record["action"] in agreement_actions(s):
                record["fulfillment"] = "consent_recorded"
            capacity -= 1

def available_requests(s, actor_id, state=None):
    if actor_id not in s.get("actors", {}):
        raise ValueError("unknown actor")
    return {name: {"description": spec["description"]}
            for name, spec in s.get("action_catalog", {}).items()
            if actor_id in spec["actors"] and (state is None or not any(
                "outcome" in a and a["consent"].get(actor_id) == name and
                (state["minute"] >= a["due_minute"] or any(
                    r["actor"] == actor_id and r["action"] == name for r in state["requests"]))
                for a in s.get("agreements", {}).values()))}

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
    if record["action"] not in available_requests(s, actor_id, state):
        raise ValueError("consent already submitted or deadline passed")
    return {**record, "turn": state["turn"], "minute": state["minute"]}
