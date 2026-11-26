"""Bounded, replayable investigation trial. Not the full AIMythos ruleset."""
import copy
import hashlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from age_runtime.core.runner import save

ROOT = Path(__file__).resolve().parents[2] / "campaigns" / "mythos"

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
            "discoveries": [], "used": [], "history": [], "ending": None,
            "resources": copy.deepcopy(rules["resources"]), "sanity": 0,
            "fatigue": 0, "containment": 0, "last_result": None,
            "relationships": copy.deepcopy(rules["relationships"]), "flags": [],
            "observations": [], "events_seen": []}

def options(state, rules):
    if state["ending"]:
        return []
    candidates = [a for a in rules["actions"] if (a.get("repeatable") or a["id"] not in state["used"])
                  and len(state["discoveries"]) >= a.get("requires", 0)
                  and all(f in state["flags"] for f in a.get("requires_flags", []))
                  and all(state["relationships"][k] >= v for k, v in a.get("requires_relationship", {}).items())] + [
                      {"id":"observe", "label":"Spend time observing the surroundings", "location":state["location"], "minutes":30}]
    remaining = (datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds() / 60
    return [a for a in candidates if a["minutes"] <= remaining
            and all(state["resources"][k] >= v for k, v in a.get("cost", {}).items())]

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
    state["location"] = a.get("location", state["location"])
    if action != "observe" and not a.get("repeatable"):
        state["used"].append(action)
    for key, amount in a.get("cost", {}).items():
        state["resources"][key] -= amount
    success = True
    if "attribute" in a:
        rng = random.Random(digest([state["seed"], state["turn"]]))
        total = (rng.randint(1, 6) + rng.randint(1, 6)
                 + state["attributes"][a["attribute"]]
                 + rules["conditions"]["sanity_dm"][state["sanity"]]
                 + rules["conditions"]["fatigue_dm"][state["fatigue"]])
        success = total >= a["tn"]
    if success:
        if "discovery" in a and a["discovery"] not in state["discoveries"]:
            state["discoveries"].append(a["discovery"])
        for flag in a.get("grant", []):
            if flag not in state["flags"]:
                state["flags"].append(flag)
        for key, delta in a.get("relationship", {}).items():
            state["relationships"][key] = max(0, min(5, state["relationships"][key] + delta))
    effects = a.get("success" if success else "failure", {})
    for key, delta in effects.items():
        state[key] = max(0, min(5, state[key] + delta))
    if state["turn"] % 4 == 0 and action not in ("rest_room", "buy_meal"):
        state["fatigue"] = min(5, state["fatigue"] + 1)
    for event in rules.get("events", []):
        if event["id"] not in state["events_seen"] and elapsed >= datetime.fromisoformat(event["at"]):
            state["events_seen"].append(event["id"])
            state["observations"].append(event["observation"])
    state["last_result"] = {"action": action, "success": success}
    state["history"].append(action)
    if a.get("terminal") or state["turn"] >= rules["max_turns"] or not options(state, rules):
        state["ending"] = {"reason": action if a.get("terminal") else "limit",
                           "evidence_count": len(state["discoveries"]),
                           "account_prepared": "written_account" in state["flags"],
                           "account_relayed": "account_relayed" in state["flags"],
                           "account_entrusted": "account_entrusted" in state["flags"],
                           "epilogue": rules["ending_text"][action if a.get("terminal") else "limit"],
                           "scores": scores(state, action)}
    return state

def scores(state, action):
    # Provisional trial rubric; integer tenths avoid floating point accumulation.
    truth = min(100, 10 + 8 * len(state["discoveries"]) + (10 if "written_account" in state["flags"] else 0)
                + (20 if "account_relayed" in state["flags"] else 15 if "account_entrusted" in state["flags"] else 0))
    self_preserved = max(10, 100 - 12 * state["sanity"] - 6 * state["fatigue"])
    contained = min(100, 10 + 18 * state["containment"])
    return {"Truth Preserved": truth / 10, "Self Preserved": self_preserved / 10,
            "Horror Contained": contained / 10}

def verify(state):
    replay = initial(state["scenario"], state["seed"])
    for action in state["history"]:
        replay = step(replay, action)
    if replay != state:
        raise ValueError("session replay mismatch")

def view(state):
    _, rules = load(state["scenario"])
    return {k: state[k] for k in ("scenario","time","location","turn","discoveries","observations","ending","last_result")} | {
        "inventory": [item for item in state["inventory"] if not item.startswith(("$", "Flask"))],
        "resources": state["resources"],
        "condition": {"sanity": rules["conditions"]["sanity"][state["sanity"]],
                      "fatigue": rules["conditions"]["fatigue"][state["fatigue"]]},
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
