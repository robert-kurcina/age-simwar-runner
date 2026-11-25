"""Local campaign catalog. Listing does not start or modify a session."""
import argparse
import json
from pathlib import Path
from runner import validate

def load_campaign(path):
    path = Path(path).resolve()
    root = path.parent
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or set(data) != {"version", "id", "title", "groups"}:
        raise ValueError("invalid campaign fields")
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("unsupported campaign version")
    def nonempty(value):
        return isinstance(value, str) and bool(value.strip())
    if not all(nonempty(data[k]) for k in ("id", "title")):
        raise ValueError("invalid campaign identity")
    if not isinstance(data["groups"], list) or not data["groups"]:
        raise ValueError("campaign requires groups")
    groups, scenarios = set(), {}
    for group in data["groups"]:
        if not isinstance(group, dict) or set(group) != {"id", "title", "scenarios"}:
            raise ValueError("invalid group fields")
        if not nonempty(group["id"]) or not nonempty(group["title"]) or group["id"] in groups:
            raise ValueError("invalid or duplicate group ID")
        groups.add(group["id"])
        if not isinstance(group["scenarios"], list) or not group["scenarios"]:
            raise ValueError("group requires scenarios")
        for entry in group["scenarios"]:
            if not isinstance(entry, dict) or not {"id", "title", "scope", "file"} <= entry.keys() or entry.keys() - {"id", "title", "scope", "file", "prerequisites"}:
                raise ValueError("invalid scenario entry fields")
            if not all(nonempty(entry[k]) for k in ("id", "title", "scope", "file")):
                raise ValueError("invalid scenario entry")
            sid = entry["id"]
            if sid in scenarios:
                raise ValueError("duplicate scenario ID: " + sid)
            ref = Path(entry["file"])
            target = (root / ref).resolve()
            if ref.is_absolute() or not target.is_relative_to(root):
                raise ValueError("scenario reference must remain within campaign directory")
            if not target.is_file():
                raise ValueError("missing scenario file: " + entry["file"])
            scenario = json.loads(target.read_text())
            validate(scenario)
            if scenario["id"] != sid:
                raise ValueError("scenario ID mismatch: " + sid)
            deps = entry.get("prerequisites", [])
            if not isinstance(deps, list) or not all(nonempty(d) for d in deps) or len(set(deps)) != len(deps):
                raise ValueError("invalid prerequisites: " + sid)
            scenarios[sid] = deps
    for sid, deps in scenarios.items():
        if any(dep not in scenarios for dep in deps):
            raise ValueError("missing prerequisite: " + sid)
    visiting, visited = set(), set()
    def visit(sid):
        if sid in visiting:
            raise ValueError("cyclic prerequisites: " + sid)
        if sid in visited:
            return
        visiting.add(sid)
        for dep in scenarios[sid]:
            visit(dep)
        visiting.remove(sid)
        visited.add(sid)
    for sid in scenarios:
        visit(sid)
    return data

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    try:
        data = load_campaign(args.manifest)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    if args.validate:
        print(json.dumps({"campaign": data["id"], "valid": True,
                          "scenarios": sum(len(g["scenarios"]) for g in data["groups"])}))
    else:
        print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
