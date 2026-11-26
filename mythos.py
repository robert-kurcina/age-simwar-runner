"""Bounded, replayable investigation trial. Not the full AIMythos ruleset."""
import copy
import hashlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from runner import save

ROOT = Path(__file__).resolve().parent / "campaigns" / "mythos"

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def load(sid):
    entry = next((s for s in read(ROOT / "campaign.json")["scenarios"] if s["id"] == sid), None)
    if not entry or entry["status"] != "trial":
        raise ValueError("scenario is not yet executable")
    return read(ROOT / entry["file"])["story_config"], read(ROOT / entry["rules"])

def initial(sid, seed):
    story, rules = load(sid)
    return {"scenario": sid, "seed": seed, "source": digest([story, rules]),
            "time": rules["start"], "location": rules["start_location"], "turn": 0,
            "inventory": story["protagonist"]["starting_inventory"],
            "attributes": story["protagonist"]["default_attributes"],
            "discoveries": [], "used": [], "history": [], "ending": None}

def options(state, rules):
    if state["ending"]:
        return []
    candidates = [a for a in rules["actions"] if a["id"] not in state["used"]
                  and len(state["discoveries"]) >= a.get("requires", 0)] + [
                      {"id":"observe", "label":"Spend time observing the surroundings", "location":state["location"], "minutes":30}]
    remaining = (datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds() / 60
    return [a for a in candidates if a["minutes"] <= remaining]

def step(state, action):
    state = copy.deepcopy(state)
    _, rules = load(state["scenario"])
    a = next((a for a in options(state, rules) if a["id"] == action), None)
    if a is None:
        raise ValueError("action unavailable")
    elapsed = datetime.fromisoformat(state["time"]) + timedelta(minutes=a["minutes"])
    if elapsed > datetime.fromisoformat(rules["end"]):
        raise ValueError("action exceeds scenario deadline")
    state["turn"] += 1
    state["time"] = elapsed.isoformat()
    state["location"] = a["location"]
    if action != "observe":
        state["used"].append(action)
    if "attribute" in a:
        rng = random.Random(digest([state["seed"], state["turn"]]))
        total = rng.randint(1,6) + rng.randint(1,6) + state["attributes"][a["attribute"]]
        if total >= a["tn"]:
            state["discoveries"].append(a["discovery"])
    state["history"].append(action)
    if a.get("terminal") or state["turn"] >= rules["max_turns"] or not options(state, rules):
        state["ending"] = {"reason": action if a.get("terminal") else "limit",
                           "evidence_count": len(state["discoveries"]),
                           "account_prepared": action == "report"}
    return state

def verify(state):
    replay = initial(state["scenario"], state["seed"])
    for action in state["history"]:
        replay = step(replay, action)
    if replay != state:
        raise ValueError("session replay mismatch")

def view(state):
    _, rules = load(state["scenario"])
    return {k: state[k] for k in ("scenario","time","location","turn","inventory","discoveries","ending")} | {
        "revision": digest(state), "opening": rules["opening"] if not state["turn"] else None,
        "choices": [{"id": a["id"], "label": a["label"]} for a in options(state, rules)]}

def start(sid, path, seed):
    if path.exists():
        raise ValueError("session already exists")
    state = initial(sid, seed)
    save(path, state)
    return view(state)

def inspect(path):
    state = read(path)
    verify(state)
    return view(state)

def act(path, action, revision):
    state = read(path)
    verify(state)
    if digest(state) != revision:
        raise ValueError("stale session revision")
    state = step(state, action)
    verify(state)
    save(path, state)
    return view(state)
