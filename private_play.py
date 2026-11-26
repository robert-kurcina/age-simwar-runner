"""Trusted local private campaign discovery and actor-bound session adapter."""
import argparse
import json
from pathlib import Path
from datetime import timedelta
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
    # Reuse reviewed civilian mechanics rather than scenario-specific identities.
    if s["events"] or s["constraints"] or s.get("civic_agreement"):
        raise ValueError("unsupported private scenario mechanics")
    keys = set(s["initial"])
    requests = set(s.get("action_catalog", {}))
    assistance = (s.get("community_assistance") is True
                  and bool(s.get("assistance_capacity"))
                  and not s.get("service_restoration")
                  and keys == {"households_assisted", "aid_packages"}
                  and requests == {"deliver_aid"})
    restoration = (s.get("service_restoration") is True
                   and not s.get("community_assistance")
                   and "assistance_capacity" not in s
                   and keys == {"open_service_centers", "restoration_credits"}
                   and requests == {"restore_service_center"})
    if not (assistance or restoration):
        raise ValueError("unsupported private scenario mechanics")


def select(path, scenario_id, owners):
    catalog = inventory(path)
    matches = [(g, e) for g in catalog["groups"] for e in g["scenarios"]
               if e["id"] == scenario_id]
    if len(matches) != 1:
        raise ValueError("scenario not found")
    group, entry = matches[0]
    if entry["status"] not in {"verified-illustrative-pilot", "reviewed-illustrative"} or group["status"] != "supported-pilot":
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


def reviewed_context(entry, compiled, actor, effective_date):
    """Pin author-reviewed, perspective-specific summaries, not raw corpus prose."""
    records = entry.get("briefing_context", [])
    if not isinstance(records, list):
        raise ValueError("invalid briefing context")
    result = []
    seen = set()
    for item in records:
        if not isinstance(item, dict) or set(item) != {
                "id", "summary", "evidence", "actors", "known_from", "reviewed_for"}:
            raise ValueError("invalid context record")
        if (not isinstance(item["id"], str) or not item["id"].strip()
                or item["id"] in seen or not isinstance(item["summary"], str)
                or not item["summary"].strip()):
            raise ValueError("invalid context identity or summary")
        seen.add(item["id"])
        actors = item["actors"]
        if (not isinstance(actors, list) or not actors
                or any(not isinstance(a, str) or a not in compiled["scenario"].get("actors", {}) for a in actors)
                or len(set(actors)) != len(actors)):
            raise ValueError("invalid context audience")
        evidence = item["evidence"]
        if not isinstance(evidence, str) or evidence not in compiled.get("evidence", {}):
            raise ValueError("context requires compiled evidence")
        ref = compiled["evidence"][evidence]
        if item["reviewed_for"] != effective_date or ref["reviewed_for"] != effective_date:
            raise ValueError("context review date mismatch")
        known = checked_date(item["known_from"])
        if known > checked_date(effective_date):
            raise ValueError("future context cannot enter opening briefing")
        if actor in actors:
            result.append({"id": item["id"], "summary": item["summary"],
                           "classification": ref["classification"],
                           "known_from": item["known_from"],
                           "evidence": evidence,
                           "section_sha256": ref["section_sha256"]})
    return result


def start(path, scenario_id, actor, owners):
    catalog, group, entry, spec, compiled = select(path, scenario_id, owners)
    s = compiled["scenario"]
    state = initialize(s)
    observe(s, state, actor)
    header = {"campaign": catalog["id"], "group": group["id"],
              "title": entry["title"], "catalog_digest": digest(catalog),
              "effective_date": spec["effective_date"], "actor": actor,
              "compiled": compiled,
              "briefing_context": reviewed_context(entry, compiled, actor, spec["effective_date"])}
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


def briefing(session):
    """Actor-visible facts only; never expose source excerpts or full checkpoints."""
    current = view(session)
    h = session["header"]
    observation = current["observation"]
    s = h["compiled"]["scenario"]
    actor = s["actors"][h["actor"]]
    start_date = checked_date(h["effective_date"])
    elapsed = observation["minute"]
    context = h.get("briefing_context", [])
    return {
        "kind": "opening" if observation["turn"] == 0 else "turn",
        "campaign": current["campaign"], "scenario": current["title"],
        "perspective": actor["label"],
        "date": (start_date + timedelta(days=elapsed // 1440)).isoformat(),
        "elapsed_minutes": elapsed, "turn": observation["turn"],
        "complete": current["complete"],
        "objectives": {oid: {"description": obj["description"],
                            "observed_result": observation["objectives"].get(oid)}
                       for oid, obj in actor.get("objectives", {}).items()},
        "reports": observation["reports"],
        "own_requests": observation["own_requests"],
        "available_requests": observation["available_requests"],
        "context": context,
        "context_status": "reviewed perspective summaries" if context else "source references pinned; player-safe narrative not yet supplied",
        "calibration": "illustrative scenario assumptions; not a historical forecast"
    }


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
    for name in ("inspect", "briefing", "submit", "advance"):
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
            if a.command not in ("inspect", "briefing"):
                session = update(session, getattr(a, "request", None), getattr(a, "turns", 0))
                save(a.session, session)
            result = briefing(session) if a.command == "briefing" else view(session)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
