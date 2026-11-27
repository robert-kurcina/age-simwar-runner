"""Discover bundled campaigns; route Mythos trials without changing strategic play.py."""
import argparse
import json
from pathlib import Path
import age_runtime.mythos.mythos as mythos
from age_runtime.mythos import player_recap
from age_runtime.core.scenario_profile import profile

ROOT = Path(__file__).resolve().parents[2]

def catalog():
    result = []
    for path in sorted((ROOT / "campaigns").glob("*/campaign.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("framework") == "mythos":
            entries = data["scenarios"]
        else:
            entries = [dict(s, status="existing") for g in data["groups"] for s in g["scenarios"]]
        result.append({"id": data["id"], "title": data["title"],
                       "framework": data.get("framework", "strategic"),
                       "scenarios": [{k: s[k] for k in ("id", "title", "status")} for s in entries]})
    return result

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    describe = sub.add_parser("describe")
    describe.add_argument("campaign")
    describe.add_argument("scenario")
    start = sub.add_parser("start")
    start.add_argument("scenario")
    start.add_argument("session", type=Path)
    start.add_argument("--seed", type=int, required=True)
    for cmd in ("inspect", "recap", "act"):
        q = sub.add_parser(cmd)
        q.add_argument("session", type=Path)
        if cmd == "act":
            q.add_argument("action")
            q.add_argument("--revision", required=True)
    recall = sub.add_parser("recall")
    recall.add_argument("session", type=Path)
    recall.add_argument("query")
    recall.add_argument("--limit", type=int, default=12)
    recall.add_argument("--offset", type=int, default=0)
    gm = sub.add_parser("gm")
    gm.add_argument("session", type=Path)
    gm.add_argument("--compact", action="store_true")
    propose = sub.add_parser("propose")
    propose.add_argument("session", type=Path)
    propose.add_argument("action")
    propose.add_argument("approach")
    propose.add_argument("--intent", required=True)
    propose.add_argument("--revision", required=True)
    propose.add_argument("--nomination", type=Path)
    commit = sub.add_parser("commit")
    commit.add_argument("session", type=Path)
    commit.add_argument("action")
    commit.add_argument("context")
    commit.add_argument("--vignette", required=True)
    commit.add_argument("--revision", required=True)
    commit.add_argument("--approach")
    commit.add_argument("--intent")
    commit.add_argument("--nomination", type=Path)
    control = sub.add_parser("narrative")
    control.add_argument("session", type=Path)
    control.add_argument("kind", choices=("scene", "open", "complete", "abandon"))
    control.add_argument("id")
    control.add_argument("--label")
    control.add_argument("--revision", required=True)
    dialogue = sub.add_parser("dialogue")
    dialogue.add_argument("session", type=Path)
    dialogue.add_argument("request", type=Path)
    dialogue.add_argument("--revision", required=True)
    establish = sub.add_parser("establish")
    establish.add_argument("session", type=Path)
    establish.add_argument("request", type=Path)
    establish.add_argument("--revision", required=True)
    memory = sub.add_parser("memory")
    memory.add_argument("session", type=Path)
    memory.add_argument("event")
    memory.add_argument("--text", required=True)
    memory.add_argument("--revision", required=True)
    args = p.parse_args()
    if args.command == "list":
        result = catalog()
    elif args.command == "describe":
        result = profile(args.campaign, args.scenario)
    elif args.command == "start":
        result = mythos.start(args.scenario, args.session, args.seed)
    elif args.command == "inspect":
        result = mythos.inspect(args.session)
    elif args.command == "recap":
        result = player_recap.recap(mythos.inspect(args.session))
    elif args.command == "recall":
        result = player_recap.recall(mythos.inspect(args.session, full_history=True), args.query,
                                     limit=args.limit, offset=args.offset)
    elif args.command == "gm":
        result = mythos.inspect_gm(args.session, compact=args.compact)
    elif args.command == "propose":
        request = {"action": args.action, "approach": args.approach, "intent": args.intent}
        if args.nomination is not None:
            request["nomination"] = json.loads(args.nomination.read_text(encoding="utf-8"))
        result = mythos.act(args.session, args.action, args.revision, request)
    elif args.command == "commit":
        if bool(args.approach) != bool(args.intent):
            p.error("--approach and --intent must be supplied together")
        proposal = {"action": args.action, "approach": args.approach, "intent": args.intent} if args.approach else None
        if args.nomination is not None:
            if proposal is None:
                p.error("--nomination requires an approach and intent")
            proposal["nomination"] = json.loads(args.nomination.read_text(encoding="utf-8"))
        result = mythos.act(args.session, args.action, args.revision, proposal,
                            {"context": args.context, "level": 1, "vignette": args.vignette})
    elif args.command == "establish":
        result = mythos.establish(args.session, json.loads(args.request.read_text(encoding="utf-8")), args.revision)
    elif args.command == "dialogue":
        result = mythos.dialogue(args.session, json.loads(args.request.read_text(encoding="utf-8")), args.revision)
    elif args.command == "memory":
        result = mythos.enrich_memory(args.session, args.event, args.text, args.revision)
    elif args.command == "narrative":
        request = {"kind": args.kind, "id": args.id}
        if args.label is not None:
            request["label"] = args.label
        result = mythos.narrative(args.session, request, args.revision)
    else:
        result = mythos.act(args.session, args.action, args.revision)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
