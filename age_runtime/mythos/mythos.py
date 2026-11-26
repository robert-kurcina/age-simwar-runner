"""Bounded, replayable investigation trial. Not the full AIMythos ruleset."""
import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from age_runtime.core.runner import save
from age_runtime.core import dxd, dxd_conditions, dxd_inspiration

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

def npc_profiles(story, rules):
    """Bind active NPCs to original authored identities and capabilities."""
    source = {n["name"]: n for n in story["antagonists"]["key_npcs"]}
    profiles = {}
    for nid, cfg in rules.get("npcs", {}).items():
        n = source[cfg["source_name"]]
        profiles[nid] = {
            "name": n["name"], "public_role": cfg["public_role"],
            "location": cfg["location"], "motivation": n["motivation"],
            "attributes": copy.deepcopy(n["attributes"]),
            "traits": copy.deepcopy(n["traits"]), "secret": n["secret"],
            "known_topics": list(cfg["known_topics"]),
            "encounters": 0, "disclosed": [], "last_contact": None,
        }
    for a in rules["actions"]:
        if "npc" not in a:
            continue
        p = profiles[a["npc"]]
        if a.get("location") != p["location"]:
            raise ValueError("NPC interaction location mismatch")
        if "disclosure" in a and (a["disclosure"] not in p["known_topics"]
                                 or a["disclosure"] not in a.get("grant", [])):
            raise ValueError("NPC disclosure must be known and granted")
    return profiles

def initial(sid, seed):
    story, rules = load(sid)
    if rules.get("resolution") != "dxd":
        raise ValueError("unsupported narrative resolver")
    state = {"scenario": sid, "seed": seed, "source": digest([story, rules]),
            "time": rules["start"], "location": rules["start_location"], "turn": 0,
            "inventory": story["protagonist"]["starting_inventory"],
            "attributes": story["protagonist"]["default_attributes"],
            "discoveries": [], "used": [], "history": [], "ending": None,
            "resources": copy.deepcopy(rules["resources"]), "containment": 0, "last_result": None,
            "relationships": copy.deepcopy(rules["relationships"]), "flags": [],
            "observations": [], "events_seen": [], "npcs": npc_profiles(story, rules)}
    if rules.get("resolution") == "dxd":
        cfg = rules["dxd"]
        dxd.validate_attributes(cfg["attributes"])
        for record in cfg["npc_attributes"].values():
            dxd.validate_attributes(record)
        for record in cfg.get("inactive_major_attributes", {}).values():
            dxd.validate_attributes(record)
        active_names = {p["name"] for p in state["npcs"].values()}
        authored_names = {p["name"] for p in story["antagonists"]["key_npcs"]}
        inactive_names = set(cfg.get("inactive_major_attributes", {}))
        if (set(cfg["npc_attributes"]) != set(state["npcs"])
                or active_names & inactive_names
                or active_names | inactive_names != authored_names):
            raise ValueError("DXD major NPC coverage mismatch")
        state["dxd"] = {"attributes": copy.deepcopy(cfg["attributes"]),
                        "skills": copy.deepcopy(cfg["skills"]),
                        "favor": cfg["favor"]["initial"], "tests": [], "inspirations": [],
                        "concerns": dxd_conditions.initial(cfg["attributes"]),
                        "inactive_major_attributes": copy.deepcopy(cfg.get("inactive_major_attributes", {}))}
        for nid, profile in state["npcs"].items():
            profile["dxd_attributes"] = copy.deepcopy(cfg["npc_attributes"][nid])
    return state

def options(state, rules):
    if state["ending"]:
        return []
    candidates = [a for a in rules["actions"] if (a.get("repeatable") or a["id"] not in state["used"])
                  and len(state["discoveries"]) >= a.get("requires", 0)
                  and all(f in state["flags"] for f in a.get("requires_flags", []))
                  and all(state["relationships"][k] >= v for k, v in a.get("requires_relationship", {}).items())
                  and ("npc" not in a or state["npcs"][a["npc"]]["location"] == a.get("location"))
                  and ("disclosure" not in a or a["disclosure"] not in state["npcs"][a["npc"]]["disclosed"])] + [
                      {"id":"observe", "label":"Spend time observing the surroundings", "location":state["location"], "minutes":30}]
    remaining = (datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds() / 60
    return [a for a in candidates if a["minutes"] <= remaining
            and all(state["resources"][k] >= v for k, v in a.get("cost", {}).items())]

def resolve_dxd(state, rules, action):
    """Gather only authored applicable modifiers and allocate Favor before rolling."""
    spec = action["test"]
    cfg = rules["dxd"]
    pc = state["dxd"]
    attr = dxd.attribute_dm(pc["attributes"][spec["attribute"]])
    skill = pc["skills"].get(spec.get("skill"), 0)
    condition = dxd_conditions.penalty_dice(pc["concerns"], decision=spec.get("decision", False))
    hook = 1 if spec.get("relationship_bonus") and state["relationships"][spec["relationship_bonus"]] >= 1 else 0
    cue = spec.get("inspiration")
    inspiration_dm = dxd_inspiration.applicable_dm(pc["inspirations"], [cue["tag"]] if cue else [])
    components = [attr, skill, hook, inspiration_dm]
    policy = cfg["favor"]
    favor = dxd.automatic_favor(available=pc["favor"], maximum=policy["maximum"],
                                significance=spec["significance"], desired=policy["desired"])
    args = {"favor": favor}
    if "npc_attribute" in spec:
        npc = state["npcs"][action["npc"]]
        args.update(narrative=True, dm=sum(max(0, x) for x in components),
                    adversity=sum(max(0, -x) for x in components), adversity_dice=condition,
                    npc_dm=dxd.attribute_dm(npc["dxd_attributes"][spec["npc_attribute"]])
                           + spec.get("npc_adversity", 0))
    else:
        args.update(tn=spec["tn"], dm=sum(components), penalty=condition)
    pc["favor"] -= favor
    chance = dxd_inspiration.probability(**args)
    first = dxd.test(digest([state["seed"], state["turn"]]), **args)
    result = first
    inspired = None
    if (not first["passed"] and cue and cfg.get("inspiration", {}).get("enabled")
            and dxd_inspiration.eligible(chance, turn=state["turn"],
                last_turn=pc["inspirations"][-1]["turn"] if pc["inspirations"] else None,
                consequence=cue["consequence"], maximum=policy["maximum"],
                extra_base=favor)):
        inspired = {"turn": state["turn"], "action": action["id"],
                    "tag": cue["tag"], "memory": cue["memory"]}
        pc["inspirations"].append(inspired)
        retry = dict(args, base=3)
        result = dxd.test(digest([state["seed"], state["turn"], "inspiration"]), **retry)
        dxd_conditions.add(pc["concerns"], weariness=1)
    pc["tests"].append({"turn": state["turn"], "action": action["id"],
                        "inputs": args, "components": {"attribute": attr, "skill": skill,
                        "condition_penalty_dice": condition, "relationship": hook,
                        "inspiration": inspiration_dm},
                        "probability": [chance.numerator, chance.denominator],
                        "initial_result": first, "inspired": inspired is not None,
                        "result": result})
    return result["passed"]

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
    npc = state["npcs"].get(a.get("npc"))
    if npc is not None:
        npc["encounters"] += 1
        npc["last_contact"] = state["time"]
    success = True
    if "test" in a:
        success = resolve_dxd(state, rules, a)
    if success:
        if "disclosure" in a:
            npc["disclosed"].append(a["disclosure"])
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
    if rules.get("resolution") == "dxd":
        concerns = state["dxd"]["concerns"]
        dxd_conditions.add(concerns, **a.get("concern_always", {}))
        dxd_conditions.add(concerns, **a.get("concern_success" if success else "concern_failure", {}))
        dxd_conditions.recover(concerns, a["minutes"], **a.get("recovery", {}))
    for event in rules.get("events", []):
        if event["id"] not in state["events_seen"] and elapsed >= datetime.fromisoformat(event["at"]):
            state["events_seen"].append(event["id"])
            if all(flag in state["flags"] for flag in event.get("visible_requires", [])):
                state["observations"].append(event["observation"])
    state["last_result"] = {"action": action, "success": success}
    if npc is not None:
        state["last_result"]["participant"] = npc["name"]
    state["history"].append(action)
    if a.get("terminal") or state["turn"] >= rules["max_turns"] or not options(state, rules):
        state["ending"] = {"reason": action if a.get("terminal") else "limit",
                           "evidence_count": len(state["discoveries"]),
                           **{key: flag in state["flags"] for key, flag in rules.get("ending_flags", {
                               "account_prepared": "written_account", "account_relayed": "account_relayed",
                               "account_entrusted": "account_entrusted"}).items()},
                           "epilogue": rules["ending_text"][action if a.get("terminal") else "limit"],
                           "scores": scores(state, action)}
    return state

def scores(state, action):
    # Provisional trial rubric; integer tenths avoid floating point accumulation.
    truth = min(100, 10 + 8 * len(state["discoveries"]) + (10 if "written_account" in state["flags"] else 0)
                + (20 if "account_relayed" in state["flags"] else 15 if "account_entrusted" in state["flags"] else 0))
    if "dxd" in state:
        concern = dxd_conditions.degrees(state["dxd"]["concerns"])
        self_preserved = max(10, 100 - 12 * concern["stress"]
                             - 6 * concern["fatigue"] - 6 * concern["weariness"])
    else:
        raise ValueError("unsupported narrative resolver")
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
        "setting": rules.get("setting", "Fear!"),
        "memories": [x["memory"] for x in state.get("dxd", {}).get("inspirations", [])],
        "contacts": [{"name": p["name"], "role": p["public_role"],
                      "encounters": p["encounters"], "last_contact": p["last_contact"]}
                     for p in state["npcs"].values() if p["encounters"]],
        "condition": dxd_conditions.describe(state["dxd"]["concerns"]),
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
