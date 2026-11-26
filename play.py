"""Trusted local referee CLI for supported civilian campaign sessions."""
import argparse
import sys
import json
from pathlib import Path
import re
from campaign import load_campaign
from continuity import export_transition, verify_transition
from runner import initialize, advance, submit_request, verify_checkpoint, digest, save
from observations import observe
from comparison import compare, summarize

VERSION = 1
SUPPORTED = {"service-restoration", "service-review", "community-assistance", "civic-agreement"}


def read(path):
    return json.loads(Path(path).read_text())


def entries(manifest):
    catalog = load_campaign(manifest)
    return catalog, {e["id"]: e for group in catalog["groups"] for e in group["scenarios"]}


def start(manifest, scenario_id, previous=None):
    catalog, index = entries(manifest)
    if scenario_id not in index or scenario_id not in SUPPORTED:
        raise ValueError("unsupported civilian scenario")
    scenario = read(Path(manifest).resolve().parent / index[scenario_id]["file"])
    transition = None
    if previous is not None:
        verify_session(previous)
        if previous["catalog_digest"] != digest(catalog):
            raise ValueError("campaign revision mismatch")
        transition = export_transition(manifest, previous["scenario"], previous["state"], scenario_id)
        scenario = transition["scenario"]
        verify_transition(manifest, previous["scenario"], previous["state"], transition)
    return {"version": VERSION, "campaign": catalog["id"], "catalog_digest": digest(catalog),
            "scenario": scenario, "state": initialize(scenario), "transition": transition}


def verify_session(session):
    if not isinstance(session, dict) or set(session) != {
            "version", "campaign", "catalog_digest", "scenario", "state", "transition"}:
        raise ValueError("invalid session bundle")
    if type(session["version"]) is not int or session["version"] != VERSION:
        raise ValueError("unsupported session version")
    if session["scenario"]["id"] not in SUPPORTED:
        raise ValueError("unsupported civilian scenario")
    if not isinstance(session["campaign"], str) or not isinstance(session["catalog_digest"], str):
        raise ValueError("invalid campaign identity")
    if not re.fullmatch(r"[0-9a-f]{64}", session["catalog_digest"]):
        raise ValueError("invalid catalog digest")
    verify_checkpoint(session["scenario"], session["state"])
    transition = session["transition"]
    if transition is not None:
        if (not isinstance(transition, dict) or
                transition.get("campaign") != session["campaign"] or
                transition.get("catalog_digest") != session["catalog_digest"] or
                transition.get("target_scenario_digest") != digest(session["scenario"]) or
                transition.get("scenario") != session["scenario"]):
            raise ValueError("transition does not match session")
    return session


def update(session, actor=None, request=None, turns=0, finish=False):
    verify_session(session)
    if type(turns) is not int or turns < 0 or (finish and turns):
        raise ValueError("invalid turn count")
    if request is not None and actor is None:
        raise ValueError("request requires actor")
    s, state = session["scenario"], session["state"]
    if actor is not None:
        observe(s, state, actor)
    if request is not None:
        state = submit_request(s, state, actor, {"action": request})
    if finish:
        turns = (s["end_minute"] - state["minute"] + s["turn_minutes"] - 1) // s["turn_minutes"]
    for _ in range(turns):
        if state["minute"] >= s["end_minute"]:
            break
        state = advance(s, state)
    result = {**session, "state": state}
    return verify_session(result)


def view(session, actor=None):
    verify_session(session)
    s, state = session["scenario"], session["state"]
    if actor is not None:
        return observe(s, state, actor)
    return {"campaign": session["campaign"], "scenario": s["id"],
            "actors": list(s.get("actors", {})), "minute": state["minute"],
            "turn": state["turn"], "complete": state["minute"] == s["end_minute"],
            "state": state}


def main():
    if sys.argv[1:2] == ['private']:
        from private_play import main as private_main
        return private_main(sys.argv[2:])
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    ls = commands.add_parser("list")
    ls.add_argument("manifest", type=Path)
    st = commands.add_parser("start")
    st.add_argument("manifest", type=Path)
    st.add_argument("scenario")
    st.add_argument("session", type=Path)
    st.add_argument("--from-session", type=Path)
    for command in ("inspect", "submit", "advance", "finish", "report"):
        sub = commands.add_parser(command)
        sub.add_argument("session", type=Path)
        if command in ("inspect", "submit", "advance", "finish"):
            sub.add_argument("--actor", required=command == "submit")
        if command == "submit":
            sub.add_argument("request")
        if command == "advance":
            sub.add_argument("--turns", type=int, default=1)
    cp = commands.add_parser("compare")
    cp.add_argument("left", type=Path)
    cp.add_argument("right", type=Path)
    args = p.parse_args()
    try:
        if args.command == "list":
            result = load_campaign(args.manifest)
        elif args.command == "start":
            if args.session.exists():
                raise ValueError("session path already exists")
            session = start(args.manifest, args.scenario,
                            read(args.from_session) if args.from_session else None)
            save(args.session, session)
            result = view(session)
        elif args.command == "compare":
            a, b = (verify_session(read(path)) for path in (args.left, args.right))
            if a["catalog_digest"] != b["catalog_digest"] or digest(a["scenario"]) != digest(b["scenario"]):
                raise ValueError("comparison requires the same campaign and scenario revision")
            result = compare(a["scenario"], a["state"], b["state"])
        else:
            session = verify_session(read(args.session))
            actor = getattr(args, "actor", None)
            if args.command == "report":
                result = summarize(session["scenario"], session["state"])
            elif args.command == "inspect":
                result = view(session, actor)
            else:
                session = update(session, actor=actor, request=getattr(args, "request", None),
                                 turns=getattr(args, "turns", 0), finish=args.command == "finish")
                save(args.session, session)
                result = view(session, actor)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
