"""Discover bundled campaigns; route Mythos trials without changing strategic play.py."""
import argparse
import json
from pathlib import Path
import age_runtime.mythos.mythos as mythos
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
    for cmd in ("inspect", "act"):
        q = sub.add_parser(cmd)
        q.add_argument("session", type=Path)
        if cmd == "act":
            q.add_argument("action")
            q.add_argument("--revision", required=True)
    control = sub.add_parser("narrative")
    control.add_argument("session", type=Path)
    control.add_argument("kind", choices=("scene", "open", "complete", "abandon"))
    control.add_argument("id")
    control.add_argument("--label")
    control.add_argument("--revision", required=True)
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
