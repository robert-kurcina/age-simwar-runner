"""Interactive local terminal interface over the existing private session API."""
import json
from pathlib import Path
from private_play import inventory, perspectives, start, verify, read, briefing, update
from player_requests import packet, confirm
from local_model import propose
from runner import save, digest


def choose(items, label, ask, emit):
    if not items:
        raise ValueError("no available " + label)
    for i, item in enumerate(items, 1):
        emit(f"{i}. {item['label']}")
    while True:
        value = ask(label + " (number, or q): ").strip()
        if value.lower() == "q":
            return None
        if value.isdecimal() and 1 <= int(value) <= len(items):
            return items[int(value) - 1]["id"]
        emit("Invalid selection.")


def render(session, emit):
    info = briefing(session)
    emit(f"\n{info['scenario']} | {info['perspective']} | {info['date']} | Turn {info['turn']}")
    emit(info["calibration"])
    if info["turn"] == 0:
        for item in info["context"]:
            emit(item["summary"])
    for key, report in info["reports"].items():
        value = report.get("value", "unknown")
        age = f"; age {report['age_minutes']} min" if "age_minutes" in report else ""
        emit(f"{key}: {value} ({report['status']}{age})")
    for obj in info["objectives"].values():
        emit(obj["description"] + ": " + json.dumps(obj["observed_result"]))
    for request in info["own_requests"]:
        emit(f"Request {request['action']}: {request['status']} / {request.get('fulfillment', 'pending')}")
    return info


def run(path, manifest=None, owners=None, model=None,
        base="http://127.0.0.1:1234/v1", ask=input, emit=print, infer=propose):
    """A trusted single-writer local session. Each confirmed change is saved."""
    path = Path(path)
    try:
        if path.exists():
            if manifest is not None or owners is not None:
                raise ValueError("resume uses pinned session; omit inventory and owners")
            session = verify(read(path))
        else:
            if manifest is None or owners is None:
                raise ValueError("new session requires inventory and owners")
            catalog = inventory(manifest)
            items = []
            for group in catalog["groups"]:
                emit(f"{group.get('title', group['id'])}: {group['status']}")
                for entry in group["scenarios"]:
                    if (group["status"] == "supported-pilot" and
                            entry["status"] in {"verified-illustrative-pilot", "reviewed-illustrative"}):
                        items.append({"id": entry["id"], "label": entry["title"]})
            selected = choose(items, "Scenario", ask, emit)
            if selected is None:
                return
            actor = choose(perspectives(manifest, selected, owners), "Perspective", ask, emit)
            if actor is None:
                return
            session = start(manifest, selected, actor, owners)
            if path.exists():
                raise ValueError("session path already exists")
            save(path, session)
        while True:
            info = render(session, emit)
            if info["complete"]:
                emit("Scenario complete. Session saved.")
                return
            actions = info["available_requests"]
            for action, item in actions.items():
                emit(f"{action}: {item['description']}")
            emit("Commands: action ID | next | quit" + (" | say <request> | narrative" if model else ""))
            command = ask("> ").strip()
            if command == "quit":
                return
            before = digest(session)
            try:
                if command == "narrative" and model:
                    from narrative import narrate
                    comment = narrate(session, model, base)
                    emit("Unverified model commentary:")
                    emit(comment["summary"])
                    continue
                if command == "next":
                    candidate = update(session, turns=1)
                elif command in actions:
                    if ask(f"Confirm {command}? [y/N] ").strip().lower() != "y":
                        continue
                    candidate = update(session, request=command)
                elif command.startswith("say ") and model:
                    instruction = command[4:].strip()
                    result = infer(session, instruction, model, base)
                    action = result["proposal"]["action"]
                    if action is None:
                        emit("No clear supported action. Choose an action ID manually.")
                        continue
                    emit(f"Proposed: {action} — {actions[action]['description']}")
                    if ask("Confirm proposal? [y/N] ").strip().lower() != "y":
                        continue
                    candidate = confirm(session, packet(session, instruction), result["response"], action)
                else:
                    emit("Unknown command. Choose a listed action or next.")
                    continue
            except (ValueError, KeyError, TypeError, OSError) as exc:
                emit(f"Request not applied: {exc}. Manual actions remain available.")
                continue
            if digest(verify(read(path))) != before:
                raise ValueError("session changed on disk; reopen before continuing")
            save(path, candidate)
            session = candidate
    except (EOFError, KeyboardInterrupt):
        emit("\nExited. Previously confirmed changes remain saved.")
