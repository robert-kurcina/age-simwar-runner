"""Owned mortal stocks: explicit units, gross debits, and dated sources/sinks.

Stocks are not divine reserve capacity. All changes use strategic values and
ledger. No automatic conversions or production from population.
"""
from collections import defaultdict
from age_runtime.core.reserve_accounting import keys as reserve_keys, _change


def validate(s):
    if not any(k in s for k in ("stock_accounts", "stock_actions", "stock_flows")):
        return
    accounts = s.get("stock_accounts")
    actions = s.get("stock_actions", {})
    flows = s.get("stock_flows", [])
    if not isinstance(accounts, dict) or not accounts or not isinstance(actions, dict) or not isinstance(flows, list):
        raise ValueError("invalid stock accounting fields")
    if any(k in s for k in ("economy_projects", "capacity_actions", "funding_reserves",
                            "resource_transfers", "agreements", "dynamic_negotiation",
                            "event_templates", "service_restoration", "community_assistance",
                            "civic_agreement", "assistance_capacity", "permission_terms")):
        raise ValueError("stock accounting cannot mix legacy fulfillment writers yet")
    used = reserve_keys(s)
    external = {e["key"] for e in s["events"]} | {k for e in s.get("dependent_events", []) for k in e["updates"]}
    for aid, a in accounts.items():
        if (not isinstance(aid, str) or not aid or not isinstance(a, dict)
                or set(a) != {"owner", "key", "unit"}
                or any(not isinstance(v, str) or not v.strip() for v in a.values())):
            raise ValueError("invalid stock account")
        key, owner = a["key"], a["owner"]
        if (owner not in s.get("actors", {}) or key not in s["initial"]
                or key in used or key in external or s["initial"][key] < 0):
            raise ValueError("invalid or overlapping stock binding")
        used.add(key)
        profile = s["actors"][owner]
        if key not in profile.get("visible_keys", []) or profile.get("report_delay_minutes", {}).get(key, 0):
            raise ValueError("stock owner requires current visibility")
    for name, a in actions.items():
        if (name not in s.get("action_catalog", {}) or not isinstance(a, dict)
                or set(a) != {"source", "destination", "amount", "purpose"}
                or not isinstance(a["source"], str) or a["source"] not in accounts
                or type(a["amount"]) is not int or a["amount"] <= 0
                or not isinstance(a["purpose"], str) or not a["purpose"].strip()):
            raise ValueError("invalid stock action")
        source, destination = accounts[a["source"]], a["destination"]
        if s["action_catalog"][name]["actors"] != [source["owner"]]:
            raise ValueError("only stock owner can authorize debit")
        if destination is not None:
            if (not isinstance(destination, str) or destination not in accounts
                    or destination == a["source"] or accounts[destination]["unit"] != source["unit"]):
                raise ValueError("transfer requires distinct same-unit accounts")
    reserve_actions = set(s.get("reserve_actions", {}))
    if reserve_actions & actions.keys() or reserve_actions | actions.keys() != set(s.get("action_catalog", {})):
        raise ValueError("stock/reserve actions must partition catalog")
    ids = set()
    for f in flows:
        if (not isinstance(f, dict) or set(f) != {"id", "account", "minute", "kind", "amount", "basis"}
                or any(not isinstance(f[k], str) or not f[k].strip() for k in ("id", "account", "basis"))
                or f["id"] in ids or f["account"] not in accounts
                or f["kind"] not in ("production", "loss")
                or type(f["amount"]) is not int or f["amount"] <= 0
                or type(f["minute"]) is not int or not 0 < f["minute"] <= s["end_minute"]
                or f["minute"] % s["turn_minutes"]):
            raise ValueError("invalid dated stock flow")
        ids.add(f["id"])
    if s["end_minute"] % s["turn_minutes"]:
        raise ValueError("stock accounting requires complete intervals")


def resolve(s, state, minute, reviewed):
    accounts, actions = s.get("stock_accounts", {}), s.get("stock_actions", {})
    if not accounts:
        return
    opening = {aid: state["values"][a["key"]] for aid, a in accounts.items()}
    rows = [(r, actions[r["action"]]) for r in reviewed if r["action"] in actions]
    gross = defaultdict(int)
    for _, a in rows:
        gross[a["source"]] += a["amount"]
    for r, a in rows:
        source, destination, amount = a["source"], a["destination"], a["amount"]
        if gross[source] > opening[source]:
            r["fulfillment"] = "stock_allocation_conflict"
            continue
        ident = "stock-request:" + str(r["sequence"])
        _change(state, minute, ident, accounts[source]["key"], -amount)
        if destination is not None:
            _change(state, minute, ident, accounts[destination]["key"], amount)
        r["fulfillment"] = "stock_transferred" if destination is not None else "stock_expended"
    # Dated loss occurs after orders, before new production. Loss is bounded
    # by actual remaining inventory; neither incoming funds nor production
    # can finance orders evaluated against opening balances.
    for f in sorted(s.get("stock_flows", []), key=lambda f: (f["kind"] != "loss", f["id"])):
        if f["minute"] != minute:
            continue
        key = accounts[f["account"]]["key"]
        amount = f["amount"] if f["kind"] == "production" else -min(f["amount"], state["values"][key])
        _change(state, minute, "stock-flow:" + f["id"], key, amount)
    if any(state["values"][a["key"]] < 0 for a in accounts.values()):
        raise ValueError("negative stock invariant violated")
