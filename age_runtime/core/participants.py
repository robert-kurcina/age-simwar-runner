"""Compile dated participant profiles; no decision policy or gameplay effects."""
import copy
import re
from age_runtime.core.runner import digest
from age_runtime.core.source_compiler import checked_date, resolve_reference, resolve_evidence

ID = re.compile(r"[a-z0-9][a-z0-9_.-]*")
KINDS = {"individual", "organization"}
GROUPS = {"identity", "capabilities", "resources", "motivations", "commitments",
          "relationships", "knowledge", "conditions", "behavior"}

def nonblank(v):
    return isinstance(v, str) and bool(v.strip())

def identifier(v):
    return isinstance(v, str) and ID.fullmatch(v) is not None

def compile_profile(spec, owners):
    fields = {"version", "world", "id", "kind", "effective_date", "label",
              "rules_namespace", "properties"}
    if not isinstance(spec, dict) or set(spec) != fields:
        raise ValueError("invalid participant profile fields")
    if type(spec["version"]) is not int or spec["version"] != 1:
        raise ValueError("unsupported participant profile version")
    if not all(identifier(spec[k]) for k in ("world", "id", "rules_namespace")):
        raise ValueError("invalid participant namespace or ID")
    if spec["kind"] not in KINDS or not nonblank(spec["label"]):
        raise ValueError("invalid participant identity")
    effective = checked_date(spec["effective_date"])
    properties = spec["properties"]
    if not isinstance(properties, dict) or not properties:
        raise ValueError("missing participant properties")
    out = copy.deepcopy(spec)
    for key, record in sorted(properties.items()):
        if not identifier(key) or "." not in key or key.split(".")[0] not in GROUPS:
            raise ValueError("invalid property namespace")
        if not isinstance(record, dict) or not nonblank(record.get("unit")):
            raise ValueError("property requires explicit unit or scale")
        if set(record) == {"unit", "reference"}:
            value, provenance = resolve_reference(record["reference"], owners, effective)
            out["properties"][key] = {"value": value, "unit": record["unit"],
                "classification": provenance["classification"], "provenance": provenance}
        elif set(record) in ({"unit", "value", "classification", "reason"},
                             {"unit", "value", "classification", "reason", "evidence"}):
            classification = record["classification"]
            value = record["value"]
            if classification not in {"hypothetical", "unresolved"} or not nonblank(record["reason"]):
                raise ValueError("literal requires hypothetical or unresolved classification and reason")
            if classification == "unresolved":
                if value is not None:
                    raise ValueError("unresolved value must be null")
            elif not (type(value) in (int, bool) or nonblank(value)):
                raise ValueError("hypothetical value must be integer, boolean or nonempty text")
            if "evidence" in record:
                if not isinstance(record["evidence"], dict) or record["evidence"].get("reviewed_for") != spec["effective_date"]:
                    raise ValueError("evidence review date differs from profile")
                out["properties"][key]["evidence"] = resolve_evidence(record["evidence"], owners)
        else:
            raise ValueError("invalid property record")
    return {"version": 1, "spec_digest": digest(spec),
            "profile_digest": digest(out), "profile": out}
