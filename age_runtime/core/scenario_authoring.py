"""Validate LLM-authored self-contained scenario candidates without registration."""
import argparse
import json
import tempfile
from pathlib import Path
from age_runtime.core.private_play import read, eligible_perspectives
from age_runtime.core.scenario_preparation import prepare
from age_runtime.core.runner import digest
import re


def review_candidate(candidate):
    """Use the actual preparation workflow against an isolated draft inventory."""
    if not isinstance(candidate, dict) or set(candidate) != {"title", "spec", "player_factions", "assumptions"}:
        raise ValueError("invalid authoring candidate fields")
    spec = candidate["spec"]
    sid = spec["scenario"]["id"]
    if not isinstance(sid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sid):
        raise ValueError("invalid scenario identity")
    if not isinstance(candidate["title"], str) or not candidate["title"].strip():
        raise ValueError("missing scenario title")
    assumptions = candidate["assumptions"]
    if not isinstance(assumptions, list) or not assumptions or any(
            not isinstance(a, str) or not a.strip() for a in assumptions):
        raise ValueError("explicit authoring assumptions required")
    if not isinstance(candidate["player_factions"], list) or not candidate["player_factions"]:
        raise ValueError("explicit player perspectives required")
    entry = {"id": sid, "title": candidate["title"], "spec": "scenario-spec.json",
             "status": "draft-unreviewed", "player_factions": candidate["player_factions"]}
    eligible_perspectives(entry, spec["scenario"])
    catalog = {"version": 1, "id": "candidate-review", "title": "Unreviewed candidate",
               "groups": [{"id": "candidate", "title": "Candidate", "status": "provisional",
                           "scenarios": [entry]}]}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "scenario-spec.json").write_text(json.dumps(spec, allow_nan=False), encoding="utf-8")
        path = root / "inventory.json"
        path.write_text(json.dumps(catalog, allow_nan=False), encoding="utf-8")
        report = prepare(path)
    result = report["results"][0]
    ready = (result["checks"].get("rehearsal", {}).get("status") == "passed"
             and report["resource_discovery_error"] is None)
    return {"candidate_digest": digest(candidate), "status": "rehearsable-unreviewed" if ready else "blocked",
            "assumptions": assumptions, "preparation": report,
            "author_review": "pending", "registered": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    try:
        report = review_candidate(read(args.candidate))
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "blocked":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
