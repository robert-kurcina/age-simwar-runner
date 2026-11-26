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
    if s["events"] or s["constraints"]:
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
    agreement = (s.get("civic_agreement") is True
                 and not s.get("community_assistance") and not s.get("service_restoration")
                 and "assistance_capacity" not in s
                 and keys == {"participating_councils", "council_a_joined", "council_b_joined"}
                 and requests == {"join_council_a", "join_council_b"}
                 and set(s.get("actors", {})) == {"council_a", "council_b"}
                 and s["initial"]["participating_councils"] == s["initial"]["council_a_joined"] + s["initial"]["council_b_joined"])
    if (assistance or restoration) and s.get("civic_agreement"):
        raise ValueError("mixed mechanics unsupported")
    if not (assistance or restoration or agreement):
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


def available_presets(path, scenario_id, owners):
    from presets import options
    _, _, entry, _, _ = select(path, scenario_id, owners)
    return options(entry)


def start(path, scenario_id, actor, owners, preset="standard", shared=False):
    catalog, group, entry, spec, compiled = select(path, scenario_id, owners)
    from presets import apply
    compiled, configuration = apply(entry, spec, compiled, preset)
    s = compiled["scenario"]
    supported(s)
    state = initialize(s)
    observe(s, state, actor)
    if bool(s.get("civic_agreement")) != shared:
        raise ValueError("agreement requires shared human participation; other scenarios use single perspective")
    header = {"campaign": catalog["id"], "group": group["id"],
              "title": entry["title"], "catalog_digest": digest(catalog),
              "effective_date": spec["effective_date"], "actor": actor,
              "compiled": compiled, "preset": configuration,
              "briefing_context": reviewed_context(entry, compiled, actor, spec["effective_date"])}
    if shared:
        header["shared"] = True
        header["actor_contexts"] = {a: reviewed_context(entry, compiled, a, spec["effective_date"]) for a in s["actors"]}
        header["briefing_context"] = header["actor_contexts"][actor]
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
    if bool(s.get("civic_agreement")) != h.get("shared", False):
        raise ValueError("session participation mode mismatch")
    if h.get("shared") and (set(h.get("actor_contexts", {})) != set(s["actors"]) or h["briefing_context"] != h["actor_contexts"][h["actor"]]):
        raise ValueError("shared perspective context mismatch")
    verify_checkpoint(s, session["state"])
    observe(s, session["state"], h["actor"])
    return session


def switch_perspective(session, actor):
    """Trusted local referee selects the human participant; no implicit consent."""
    verify(session)
    h = session["header"]
    if not h.get("shared"):
        raise ValueError("single-perspective session cannot switch actors")
    if actor not in h["actor_contexts"]:
        raise ValueError("unknown participant")
    header = {**h, "actor": actor, "briefing_context": h["actor_contexts"][actor]}
    return verify({**session, "header": header, "header_digest": digest(header)})


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
        "shared": h.get("shared", False),
        "preset": h.get("preset", {"id": "standard", "label": "Standard — configured baseline"}),
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
    for name in ("perspectives", "presets", "start"):
        sub = commands.add_parser(name)
        sub.add_argument("inventory")
        sub.add_argument("scenario")
        sub.add_argument("owners")
        if name == "start":
            sub.add_argument("actor")
            sub.add_argument("session", type=Path)
            sub.add_argument("--preset", default="standard")
            sub.add_argument("--shared", action="store_true")
    for name in ("inspect", "briefing", "submit", "advance"):
        sub = commands.add_parser(name)
        sub.add_argument("session", type=Path)
        if name == "submit":
            sub.add_argument("request")
        if name == "advance":
            sub.add_argument("--turns", type=int, default=1)
    for name in ("interpret", "proposal", "confirm"):
        sub = commands.add_parser(name)
        sub.add_argument("session", type=Path)
        sub.add_argument("instruction")
        if name != "interpret":
            sub.add_argument("response", type=Path)
        if name == "confirm":
            sub.add_argument("--approve", required=True)
    switch = commands.add_parser("switch")
    switch.add_argument("session", type=Path)
    switch.add_argument("actor")
    local = commands.add_parser("local-propose")
    local.add_argument("session", type=Path)
    local.add_argument("instruction")
    local.add_argument("--model", required=True)
    local.add_argument("--base", default="http://127.0.0.1:1234/v1")
    local.add_argument("--output", type=Path, required=True)
    interactive = commands.add_parser("interactive")
    interactive.add_argument("session", type=Path)
    interactive.add_argument("--inventory", type=Path)
    interactive.add_argument("--owners", type=Path)
    interactive.add_argument("--model")
    interactive.add_argument("--base", default="http://127.0.0.1:1234/v1")
    a = p.parse_args(argv)
    try:
        if a.command == "interactive":
            from interactive_play import run
            run(a.session, a.inventory, read(a.owners) if a.owners else None, a.model, a.base)
            return
        if a.command == "list":
            result = inventory(a.inventory)
        elif a.command == "perspectives":
            result = perspectives(a.inventory, a.scenario, read(a.owners))
        elif a.command == "presets":
            result = available_presets(a.inventory, a.scenario, read(a.owners))
        elif a.command == "start":
            if a.session.exists():
                raise ValueError("session path already exists")
            session = start(a.inventory, a.scenario, a.actor, read(a.owners), a.preset, a.shared)
            save(a.session, session)
            result = view(session)
        elif a.command == "switch":
            session = switch_perspective(read(a.session), a.actor)
            save(a.session, session)
            result = briefing(session)
        elif a.command == "local-propose":
            from local_model import propose
            if a.output.exists() or a.output.resolve() == a.session.resolve():
                raise ValueError("response output must be a new file")
            session = verify(read(a.session))
            result = propose(session, a.instruction, a.model, a.base)
            save(a.output, result["response"])
        elif a.command in ("interpret", "proposal", "confirm"):
            from player_requests import packet, prompt, validate_proposal, confirm
            session = verify(read(a.session))
            exchange = packet(session, a.instruction)
            if a.command == "interpret":
                result = {"exchange": exchange, "prompt": prompt(exchange)}
            elif a.command == "proposal":
                result = validate_proposal(session, exchange, read(a.response))
            else:
                session = confirm(session, exchange, read(a.response), a.approve)
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
