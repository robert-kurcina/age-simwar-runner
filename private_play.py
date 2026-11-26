"""Trusted local private campaign discovery and actor-bound session adapter."""
import argparse
import json
from pathlib import Path
from source_compiler import parse_json, compile_scenario, checked_date
from runner import initialize, verify_checkpoint, submit_request, advance, digest, save
from observations import observe


def read(path):
    return parse_json(Path(path).read_bytes())


def inventory(path):
    data = read(path)
    if data.get("version") != 1 or not isinstance(data.get("groups"), list):
        raise ValueError("invalid inventory")
    groups, scenarios = set(), set()
    for group in data["groups"]:
        if group["id"] in groups:
            raise ValueError("duplicate group")
        groups.add(group["id"])
        for entry in group["scenarios"]:
            if entry["id"] in scenarios:
                raise ValueError("duplicate scenario")
            scenarios.add(entry["id"])
    return data


def supported(s):
    # This adapter admits only the existing finite civilian assistance mechanic.
    if (s.get("community_assistance") is not True or not s.get("assistance_capacity")
            or s.get("service_restoration") or s.get("civic_agreement")
            or set(s["initial"]) != {"households_assisted", "aid_packages"}
            or s["events"] or s["constraints"]
            or set(s.get("action_catalog", {})) != {"deliver_aid"}):
        raise ValueError("unsupported private scenario mechanics")


def select(path, scenario_id, owners):
    catalog = inventory(path)
    matches = [(g, e) for g in catalog["groups"] for e in g["scenarios"]
               if e["id"] == scenario_id]
    if len(matches) != 1:
        raise ValueError("scenario not found")
    group, entry = matches[0]
    if entry["status"] != "verified-illustrative-pilot" or group["status"] != "supported-pilot":
        raise ValueError("scenario is catalog-only")
    root = Path(path).resolve().parent
    spec_path = (root / entry["spec"]).resolve()
    if not spec_path.is_relative_to(root):
        raise ValueError("scenario path outside inventory")
    spec = read(spec_path)
    compiled = compile_scenario(spec, owners)
    s = compiled["scenario"]
    supported(s)
    if s["id"] != scenario_id:
        raise ValueError("scenario identity mismatch")
    return catalog, group, entry, spec, compiled


def perspectives(path, scenario_id, owners):
    _, _, _, _, compiled = select(path, scenario_id, owners)
    return [{"id": k, "label": v["label"]} for k, v in
            compiled["scenario"].get("actors", {}).items()]


def start(path, scenario_id, actor, owners):
    catalog, group, entry, spec, compiled = select(path, scenario_id, owners)
    s = compiled["scenario"]
    state = initialize(s)
    observe(s, state, actor)
    header = {"campaign": catalog["id"], "group": group["id"],
              "title": entry["title"], "catalog_digest": digest(catalog),
              "effective_date": spec["effective_date"], "actor": actor,
              "compiled": compiled}
    return {"version": 1, "header": header, "header_digest": digest(header), "state": state}


def verify(session):
    if session.get("version") != 1 or digest(session["header"]) != session["header_digest"]:
        raise ValueError("session header mismatch")
    h = session["header"]
    checked_date(h["effective_date"])
    s = h["compiled"]["scenario"]
    if digest(s) != h["compiled"]["scenario_digest"]:
        raise ValueError("compiled scenario mismatch")
    supported(s)
    verify_checkpoint(s, session["state"])
    observe(s, session["state"], h["actor"])
    return session


def view(session):
    verify(session)
    h = session["header"]
    s = h["compiled"]["scenario"]
    return {"campaign": h["campaign"], "group": h["group"], "title": h["title"],
            "effective_date": h["effective_date"], "turn_minutes": s["turn_minutes"],
            "complete": session["state"]["minute"] == s["end_minute"],
            "observation": observe(s, session["state"], h["actor"])}


def update(session, request=None, turns=0):
    verify(session)
    if type(turns) is not int or turns < 0:
        raise ValueError("invalid turn count")
    h = session["header"]
    s, state = h["compiled"]["scenario"], session["state"]
    if request is not None:
        state = submit_request(s, state, h["actor"], {"action": request})
    for _ in range(turns):
        if state["minute"] >= s["end_minute"]:
            break
        state = advance(s, state)
    return verify({**session, "state": state})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    ls = commands.add_parser("list")
    ls.add_argument("inventory")
    for name in ("perspectives", "start"):
        sub = commands.add_parser(name)
        sub.add_argument("inventory")
        sub.add_argument("scenario")
        sub.add_argument("owners")
        if name == "start":
            sub.add_argument("actor")
            sub.add_argument("session", type=Path)
    for name in ("inspect", "submit", "advance"):
        sub = commands.add_parser(name)
        sub.add_argument("session", type=Path)
        if name == "submit":
            sub.add_argument("request")
        if name == "advance":
            sub.add_argument("--turns", type=int, default=1)
    a = p.parse_args(argv)
    try:
        if a.command == "list":
            result = inventory(a.inventory)
        elif a.command == "perspectives":
            result = perspectives(a.inventory, a.scenario, read(a.owners))
        elif a.command == "start":
            if a.session.exists():
                raise ValueError("session path already exists")
            session = start(a.inventory, a.scenario, a.actor, read(a.owners))
            save(a.session, session)
            result = view(session)
        else:
            session = verify(read(a.session))
            if a.command != "inspect":
                session = update(session, getattr(a, "request", None), getattr(a, "turns", 0))
                save(a.session, session)
            result = view(session)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
