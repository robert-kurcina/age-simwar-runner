"""Opt-in bounded reserve accounts, backed by the strategic values and ledger.

No native PR calibration or mapped PL conversion. Each persistent commitment
has its own integer slot; zero means inactive. Authored requests are reviewed
as a simultaneous batch; conflicting gross allocations fail together.
"""


def keys(s):
    return {key for account in s.get("reserve_accounts", {}).values()
            for key in [account["available"], account["depleted"],
                        *account["commitments"].values()]}


def validate(s):
    if "reserve_accounts" not in s and "reserve_actions" not in s:
        return
    accounts, actions = s.get("reserve_accounts"), s.get("reserve_actions")
    if not isinstance(accounts, dict) or not accounts or not isinstance(actions, dict) or not actions:
        raise ValueError("reserve accounts and actions required")
    # Explicitly isolate existing fulfillment mechanisms until their writer
    # ownership and cross-account semantics have been reconciled.
    if any(k in s for k in ("economy_projects", "capacity_actions", "funding_reserves",
                            "resource_transfers", "agreements", "dynamic_negotiation",
                            "event_templates", "service_restoration", "community_assistance",
                            "civic_agreement", "assistance_capacity", "permission_terms")):
        raise ValueError("reserve accounting cannot mix other fulfillment mechanisms yet")
    used = set()
    for aid, account in accounts.items():
        if (not isinstance(aid, str) or not aid or not isinstance(account, dict)
                or set(account) != {"owner", "capacity", "available", "depleted", "commitments", "recovery"}):
            raise ValueError("invalid reserve account")
        owner = account["owner"]
        if not isinstance(owner, str) or owner not in s.get("actors", {}):
            raise ValueError("unknown reserve owner")
        cap, recovery = account["capacity"], account["recovery"]
        if type(cap) is not int or cap <= 0 or type(recovery) is not int or not 0 <= recovery <= cap:
            raise ValueError("invalid reserve capacity or recovery")
        slots = account["commitments"]
        if not isinstance(slots, dict) or any(not isinstance(k, str) or not k for k in slots):
            raise ValueError("invalid commitment IDs")
        bindings = [account["available"], account["depleted"], *slots.values()]
        if (any(not isinstance(k, str) or k not in s["initial"] for k in bindings)
                or len(set(bindings)) != len(bindings) or used.intersection(bindings)):
            raise ValueError("reserve keys must be distinct existing values")
        used.update(bindings)
        values = [s["initial"][k] for k in bindings]
        if any(v < 0 for v in values) or sum(values) != cap:
            raise ValueError("reserve capacity must balance")
        profile = s["actors"][owner]
        if any(k not in profile.get("visible_keys", []) or profile.get("report_delay_minutes", {}).get(k, 0) for k in bindings):
            raise ValueError("owner requires current reserve visibility")
    external = {e["key"] for e in s["events"]} | {k for e in s.get("dependent_events", []) for k in e["updates"]}
    if used & external:
        raise ValueError("external writer cannot change reserve balances")
    for name, action in actions.items():
        if (name not in s.get("action_catalog", {}) or not isinstance(action, dict)
                or set(action) != {"account", "operation", "amount", "commitment"}):
            raise ValueError("invalid reserve action")
        aid, op, amount, commitment = (action[k] for k in ("account", "operation", "amount", "commitment"))
        if not isinstance(aid, str) or aid not in accounts or not isinstance(op, str):
            raise ValueError("invalid reserve action account or operation")
        account = accounts[aid]
        if s["action_catalog"][name]["actors"] != [account["owner"]]:
            raise ValueError("only reserve owner can authorize allocation")
        if op in ("reserve", "spend"):
            if type(amount) is not int or not 0 < amount <= account["capacity"]:
                raise ValueError("invalid reserve amount")
        elif op in ("release", "consume"):
            if amount is not None:
                raise ValueError("release or consumption resolves entire commitment")
        else:
            raise ValueError("unknown reserve operation")
        if op == "spend":
            if commitment is not None:
                raise ValueError("spending does not require commitment")
        elif not isinstance(commitment, str) or commitment not in account["commitments"]:
            raise ValueError("unknown reserve commitment")
    if set(actions) != set(s.get("action_catalog", {})):
        raise ValueError("reserve slice only supports authored reserve requests")
    if s["end_minute"] % s["turn_minutes"]:
        raise ValueError("reserve recovery requires complete intervals")


def _change(state, minute, identifier, key, delta):
    if delta:
        state["values"][key] += delta
        state["ledger"].append({"id": identifier + ":" + key, "minute": minute,
                                "key": key, "delta": delta, "value": state["values"][key]})


def resolve(s, state, minute, reviewed):
    """Resolve against one opening snapshot, then recover depleted capacity.

    Same-slot collisions reject every conflicting request. Oversubscribed
    allocations reject all otherwise eligible debits to that account.
    Releases cannot fund spending in the same batch; no submission-order bias.
    """
    actions = s.get("reserve_actions", {})
    for aid, account in sorted(s.get("reserve_accounts", {}).items()):
        opening = dict(state["values"])
        available, depleted = account["available"], account["depleted"]
        slots = account["commitments"]
        rows = [(r, actions[r["action"]]) for r in reviewed
                if r["action"] in actions and actions[r["action"]]["account"] == aid]
        counts = {}
        for _, a in rows:
            if a["commitment"] is not None:
                c = a["commitment"]
                counts[c] = counts.get(c, 0) + 1
        eligible = []
        for r, a in rows:
            op, c = a["operation"], a["commitment"]
            if c is not None and counts[c] > 1:
                r["fulfillment"] = "commitment_conflict"
            elif op == "reserve" and opening[slots[c]] != 0:
                r["fulfillment"] = "commitment_active"
            elif op in ("release", "consume") and opening[slots[c]] == 0:
                r["fulfillment"] = "commitment_inactive"
            else:
                eligible.append((r, a))
        gross = sum(a["amount"] for _, a in eligible if a["operation"] in ("reserve", "spend"))
        for r, a in eligible:
            op, c = a["operation"], a["commitment"]
            if op in ("reserve", "spend"):
                if gross > opening[available]:
                    r["fulfillment"] = "allocation_conflict"
                    continue
                changes = [(available, -a["amount"]),
                           (depleted if op == "spend" else slots[c], a["amount"])]
            else:
                n = opening[slots[c]]
                changes = [(slots[c], -n), (available if op == "release" else depleted, n)]
            for key, delta in changes:
                _change(state, minute, "reserve-request:" + str(r["sequence"]), key, delta)
            r["fulfillment"] = {"reserve": "reserved", "spend": "spent",
                                "release": "released", "consume": "consumed"}[op]
        # Recover only capacity depleted at interval opening, not expenditure
        # newly adjudicated at this boundary.
        n = min(account["recovery"], opening[depleted])
        for key, delta in ((depleted, -n), (available, n)):
            _change(state, minute, "reserve-recovery:" + aid + ":" + str(minute), key, delta)
        values = [state["values"][k] for k in [available, depleted, *slots.values()]]
        if min(values) < 0 or sum(values) != account["capacity"]:
            raise ValueError("reserve accounting invariant violated")
