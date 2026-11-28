"""Bounded strategic consequences of successfully accounted orders.

Effects represent authored net changes to non-resource world properties, not
LLM-supplied mutations. Independent orders can reinforce or oppose one another.
All effects aggregate before bounds are applied, eliminating submission bias.
"""
from collections import defaultdict
from age_runtime.core.reserve_accounting import keys as reserve_keys, _change

_SUCCESS = frozenset({"reserved", "spent", "released", "consumed",
                      "stock_transferred", "stock_expended"})


def validate(s):
    if "matrix_properties" not in s and "matrix_effects" not in s:
        return
    props, effects = s.get("matrix_properties"), s.get("matrix_effects")
    if not isinstance(props, dict) or not props or not isinstance(effects, dict) or not effects:
        raise ValueError("matrix requires properties and effects")
    actions = set(s.get("reserve_actions", {})) | set(s.get("stock_actions", {}))
    if not actions:
        raise ValueError("matrix effects require accounted orders")
    protected = reserve_keys(s) | {a["key"] for a in s.get("stock_accounts", {}).values()}
    protected |= {e["key"] for e in s["events"]}
    protected |= {k for e in s.get("dependent_events", []) for k in e["updates"]}
    for key, spec in props.items():
        if (key not in s["initial"] or key in protected or not isinstance(spec, dict)
                or set(spec) != {"minimum", "maximum"}
                or any(type(v) is not int for v in spec.values())
                or not spec["minimum"] <= s["initial"][key] <= spec["maximum"]):
            raise ValueError("invalid or overlapping matrix property")
    for action, changes in effects.items():
        if (action not in actions or not isinstance(changes, dict) or not changes
                or any(k not in props or type(v) is not int or not v for k, v in changes.items())):
            raise ValueError("invalid authored matrix effect")
        actor = s["action_catalog"][action]["actors"][0]
        profile = s["actors"][actor]
        if any(k not in profile.get("visible_keys", []) or profile.get("report_delay_minutes", {}).get(k, 0)
               for k in changes):
            raise ValueError("effect target must be currently observable by acting faction")


def resolve(s, state, minute, reviewed):
    effects = s.get("matrix_effects", {})
    totals = defaultdict(int)
    for record in reviewed:
        changes = effects.get(record["action"])
        if changes is None or record.get("fulfillment") not in _SUCCESS:
            continue
        for key, delta in changes.items():
            totals[key] += delta
        # An accounted intervention may be opposed or saturated; this records
        # its contribution, not a promise that the desired outcome occurred.
        record["matrix_contribution"] = dict(changes)
    for key, delta in sorted(totals.items()):
        spec = s["matrix_properties"][key]
        before = state["values"][key]
        after = max(spec["minimum"], min(spec["maximum"], before + delta))
        _change(state, minute, "matrix:" + str(minute), key, after - before)
