"""Bounded, replayable investigation trial. Not the full AIMythos ruleset."""
import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from age_runtime.core.runner import save
from age_runtime.core import dxd, dxd_conditions, dxd_inspiration, dxd_character, dxd_modifiers, dxd_morale, dxd_psychology

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
    if rules.get("demeanor"):
        state["relationship_changes"] = []
    if rules.get("opposition"):
        state["opposition"] = {"marks": 0, "resolved": False}
    if "progression" in rules:
        state["progression"] = {"stage": rules["progression"]["initial_stage"],
                                "arrested": False, "changes": []}
    if rules.get("resolution") == "dxd":
        cfg = rules["dxd"]
        bodies = cfg["body_profiles"]
        raw = {"pc": cfg["attributes"], **cfg["npc_attributes"],
               **cfg.get("inactive_major_attributes", {})}
        if len(raw) != 1 + len(cfg["npc_attributes"]) + len(cfg.get("inactive_major_attributes", {})) or set(raw) != set(bodies):
            raise ValueError("DXD body profile coverage mismatch")
        derived = {key: dxd_character.derive(value, bodies[key]) for key, value in raw.items()}
        active_names = {p["name"] for p in state["npcs"].values()}
        authored_names = {p["name"] for p in story["antagonists"]["key_npcs"]}
        inactive_names = set(cfg.get("inactive_major_attributes", {}))
        if (set(cfg["npc_attributes"]) != set(state["npcs"])
                or active_names & inactive_names
                or active_names | inactive_names != authored_names):
            raise ValueError("DXD major NPC coverage mismatch")
        state["dxd"] = {"attributes": derived["pc"]["attributes"], "body": derived["pc"],
                        "skills": copy.deepcopy(cfg["skills"]), "traits": copy.deepcopy(cfg.get("traits", {})),
                        "favor": cfg["favor"]["initial"], "tests": [], "inspirations": [], "memory_edits": [], "morale": dxd_morale.initial(),
                        "concerns": dxd_conditions.initial(derived["pc"]["attributes"]),
                        "inactive_major_attributes": {key: derived[key]["attributes"] for key in inactive_names},
                        "inactive_major_bodies": {key: derived[key] for key in inactive_names}}
        for nid, profile in state["npcs"].items():
            profile["dxd_attributes"] = derived[nid]["attributes"]
            profile["body"] = derived[nid]
    return state

def options(state, rules):
    if state["ending"]:
        return []
    candidates = [dict(a, minutes=int((datetime.fromisoformat(a["until"]) - datetime.fromisoformat(state["time"])).total_seconds() / 60)) if "until" in a else a for a in rules["actions"] if (a.get("repeatable") or a["id"] not in state["used"])
                  and len(state["discoveries"]) >= a.get("requires", 0)
                  and all(f in state["flags"] for f in a.get("requires_flags", []))
                  and (not a.get("requires_any_flags") or any(f in state["flags"] for f in a["requires_any_flags"]))
                  and all(f in state["used"] for f in a.get("requires_used", []))
                  and not any(f in state["flags"] for f in a.get("excludes_flags", []))
                  and all(state["relationships"][k] >= v for k, v in a.get("requires_relationship", {}).items())
                  and ("npc" not in a or state["npcs"][a["npc"]]["location"] == a.get("location"))
                  and (not a.get("available_from") or state["time"] >= a["available_from"])
                  and (not a.get("available_until") or state["time"] < a["available_until"])
                  and ("disclosure" not in a or a["disclosure"] not in state["npcs"][a["npc"]]["disclosed"])] + [
                      {"id":"observe", "label":"Spend time observing the surroundings", "location":state["location"], "minutes":rules.get("observe_minutes", 30)}]
    remaining = (datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds() / 60
    return [a for a in candidates if 0 < a["minutes"] <= remaining
            and (not a.get("available_until") or datetime.fromisoformat(state["time"]) + timedelta(minutes=a["minutes"]) <= datetime.fromisoformat(a["available_until"]))
            and all(state["resources"][k] >= v for k, v in a.get("cost", {}).items())]

def resolve_dxd(state, rules, action):
    """Gather only authored applicable modifiers and allocate Favor before rolling."""
    spec = action["test"]
    cfg = rules["dxd"]
    pc = state["dxd"]
    gathered = dxd_modifiers.gather(pc["attributes"], pc["skills"], pc["traits"], spec)
    attr = sum(x["dm"] for x in gathered["attribute"])
    skill = sum(x["dm"] for x in gathered["skill"])
    other = [x["dm"] for key in ("trait", "explicit", "interdisciplinary") for x in gathered[key]]
    mods = dxd_modifiers.totals(gathered)
    condition = dxd_conditions.penalty_dice(pc["concerns"], decision=spec.get("decision", False))
    hook = (state["relationships"].get(action.get("npc"), 0) if rules.get("demeanor") and spec["attribute"] == "PRE"
            else 1 if spec.get("relationship_bonus") and state["relationships"][spec["relationship_bonus"]] >= 1 else 0)
    cue = spec.get("inspiration")
    inspiration_dm = dxd_inspiration.applicable_dm(pc["inspirations"], [cue["tag"]] if cue else [])
    policy = cfg["favor"]
    emicted = dxd.emicted_favor(available=pc["favor"], maximum=policy["maximum"],
                                 enabled=policy.get("emicted", False))
    psychology = dxd_psychology.effects(pc["morale"], spec.get("psychology_context"))
    progression_dm = -(state["progression"]["stage"] - 1) if "progression" in state and spec["attribute"] == "POW" else 0
    components = [attr, skill, hook, inspiration_dm, emicted, spec.get("fixed_dm", 0), psychology["dm"], progression_dm] + other
    favor = dxd.automatic_favor(available=pc["favor"], maximum=policy["maximum"],
                                significance=spec["significance"], desired=policy["desired"])
    net = mods["bonus"] - mods["penalty"] - condition - psychology["penalty"]
    bonus = min(policy["maximum"], max(0, net))
    penalty = max(0, -net)
    args = {"favor": favor, "bonus": bonus}
    if "npc_attribute" in spec:
        npc = state["npcs"][action["npc"]]
        args.update(narrative=True, dm=sum(max(0, x) for x in components),
                    adversity=sum(max(0, -x) for x in components), adversity_dice=penalty,
                    npc_dm=dxd.attribute_dm(npc["dxd_attributes"][spec["npc_attribute"]])
                           + spec.get("npc_adversity", 0))
    else:
        args.update(tn=spec["tn"], dm=sum(components), penalty=penalty)
    pc["favor"] -= favor
    chance = dxd_inspiration.probability(**args)
    seed_parts = [state["seed"], state["turn"]]
    if spec.get("morale_event"):
        seed_parts.append(spec["morale_event"])
    first = dxd.test(digest(seed_parts), **args)
    result = first
    inspired = None
    if (not first["passed"] and cue and cfg.get("inspiration", {}).get("enabled")
            and dxd_inspiration.eligible(chance, turn=state["turn"],
                last_turn=pc["inspirations"][-1]["turn"] if pc["inspirations"] else None,
                consequence=cue["consequence"], maximum=policy["maximum"],
                extra_base=favor)):
        inspired = {"turn": state["turn"], "action": action["id"],
                    "tag": cue["tag"], "memory": cue["memory"],
                    "basis": cue["memory"], "source": "authored"}
        pc["inspirations"].append(inspired)
        retry = dict(args, base=3)
        result = dxd.test(digest(seed_parts + ["inspiration"]), **retry)
        dxd_conditions.add(pc["concerns"], weariness=1)
    pc["tests"].append({"turn": state["turn"], "action": action["id"],
                        "inputs": args, "components": {"attribute": attr, "skill": skill,
                        "condition_penalty_dice": condition, "relationship": hook,
                        "inspiration": inspiration_dm, "emicted": emicted, "psychology": psychology, "progression": progression_dm},
                        "gathered": gathered, "net_bonus": bonus, "net_penalty": penalty,
                        "probability": [chance.numerator, chance.denominator],
                        "initial_result": first, "inspired": inspired is not None,
                        "result": result})
    return result["passed"]

DEMEANORS = ("Violent", "Hatred", "Disrespect", "Untrusting", "Dislike", "Guarded",
             "Neutral", "Like", "Respect", "Loyal", "Trust", "Charmed", "Reverence")

def change_demeanor(state, key, delta):
    """Bound ordinary persistent changes in rolling fictional-time windows.

    Month is interpreted as 30 days. Temporary changes and exceptional
    rulings are deliberately not supported by this first implementation.
    """
    now = datetime.fromisoformat(state["time"])
    history = [e for e in state["relationship_changes"] if e["npc"] == key]
    def recent(days):
        return [e["delta"] for e in history
                if now - datetime.fromisoformat(e["at"]) < timedelta(days=days)]
    week, month = recent(7), recent(30)
    if delta > 0:
        delta = min(delta, max(0, 3 - sum(max(0, x) for x in month)))
        if any(x < 0 for x in month):
            delta = min(delta, max(0, 1 - sum(max(0, x) for x in week)))
    elif delta < 0:
        delta = -min(3, -delta + int(bool(history and history[-1]["delta"] > 0)),
                     max(0, 3 + sum(min(0, x) for x in week)))
    old = state["relationships"][key]
    new = max(-6, min(6, old + delta))
    if new != old:
        state["relationships"][key] = new
        state["relationship_changes"].append({"npc": key, "at": state["time"], "delta": new - old})

def advance_opposition(state, rules, action, success):
    """A single authored pressure clock; no duplicate exposure roll."""
    cfg = rules.get("opposition")
    if not cfg:
        return
    clock = state["opposition"]
    if clock["resolved"]:
        return
    amount = action.get("opposition_marks", 0)
    if not success:
        amount += action.get("opposition_failure_marks", 0)
    clock["marks"] = min(cfg["segments"], clock["marks"] + amount)
    if clock["marks"] == cfg["segments"]:
        clock["resolved"] = True
        state["flags"].append(cfg["grant"])
        state["observations"].append(cfg["observation"])

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
    if "progression" in state:
        advance_events(state, rules, elapsed)
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
        if a.get("arrest_progression"):
            state["progression"]["arrested"] = True
            state["progression"]["changes"].append({"at": state["time"], "kind": "arrest", "stage": state["progression"]["stage"]})
        if "disclosure" in a:
            npc["disclosed"].append(a["disclosure"])
        if "discovery" in a and a["discovery"] not in state["discoveries"]:
            state["discoveries"].append(a["discovery"])
        for flag in a.get("grant", []):
            if flag not in state["flags"]:
                state["flags"].append(flag)
        for key, delta in a.get("relationship", {}).items():
            if rules.get("demeanor"):
                change_demeanor(state, key, delta)
            else:
                state["relationships"][key] = max(0, min(5, state["relationships"][key] + delta))
    if not success and rules.get("demeanor"):
        for key, delta in a.get("relationship_failure", {}).items():
            change_demeanor(state, key, delta)
    for flag in a.get("grant_failure", []) if not success else []:
        if flag not in state["flags"]:
            state["flags"].append(flag)
    if not success and a.get("failure_observation"):
        state["observations"].append(a["failure_observation"])
    advance_opposition(state, rules, a, success)
    effects = a.get("success" if success else "failure", {})
    for key, delta in effects.items():
        state[key] = max(0, min(5, state[key] + delta))
    if rules.get("resolution") == "dxd":
        concerns = state["dxd"]["concerns"]
        dxd_conditions.add(concerns, **a.get("concern_always", {}))
        dxd_conditions.add(concerns, **a.get("concern_success" if success else "concern_failure", {}))
        before = dxd_conditions.degrees(concerns)["stress"]
        dxd_conditions.recover(concerns, a["minutes"], **a.get("recovery", {}))
        dxd_morale.calm(state["dxd"]["morale"], safe=a.get("recovery", {}).get("safe", False),
                        stress_degrees_removed=before - dxd_conditions.degrees(concerns)["stress"])
        if success and "morale_success" in a:
            hazard = a["morale_success"]
            spec = dxd_morale.specification(hazard["kind"], hazard["trigger"])
            spec["morale_event"] = a["id"] + ":morale"
            spec["inspiration"] = hazard["inspiration"]
            resolve_dxd(state, rules, {"id": spec["morale_event"], "test": spec})
            outcome = state["dxd"]["tests"][-1]["result"]
            reaction = dxd_morale.apply(state["dxd"]["morale"], concerns,
                kind=hazard["kind"], trigger=hazard["trigger"], result=outcome,
                event=spec["morale_event"], turn=state["turn"])
            if not reaction["passed"]:
                state["observations"].append(hazard["reaction"])
                if "cosmic_failure" in hazard:
                    revelation = hazard["cosmic_failure"]
                    dxd_psychology.acquire(state["dxd"]["morale"], concerns,
                        revelation=revelation["revelation"], understood=True, destabilized=True,
                        disability=revelation["disability"], turn=state["turn"])
    if "progression" not in state:
        advance_events(state, rules, elapsed)
    state["last_result"] = {"action": action, "success": success}
    if npc is not None:
        state["last_result"]["participant"] = npc["name"]
    state["history"].append(action)
    terminal = a.get("terminal") and (success or not a.get("terminal_on_success"))
    if terminal or state["turn"] >= rules["max_turns"] or not options(state, rules):
        state["ending"] = {"reason": action if terminal else "limit",
                           "evidence_count": len(state["discoveries"]),
                           **{key: flag in state["flags"] for key, flag in rules.get("ending_flags", {
                               "account_prepared": "written_account", "account_relayed": "account_relayed",
                               "account_entrusted": "account_entrusted"}).items()},
                           "epilogue": rules["ending_text"][action if terminal else "limit"],
                           "scores": scores(state, action)}
    return state

def advance_events(state, rules, elapsed):
    """Apply dated events once; long actions cannot retroactively alter earlier milestones."""
    for event in sorted(rules.get("events", []), key=lambda e: e["at"]):
        if event["id"] in state["events_seen"] or elapsed < datetime.fromisoformat(event["at"]):
            continue
        state["events_seen"].append(event["id"])
        for flag in event.get("grant", []):
            if flag not in state["flags"]:
                state["flags"].append(flag)
        progression = state.get("progression")
        if "stage" in event:
            if progression is None:
                raise ValueError("stage event requires progression")
            if not progression["arrested"] and event["stage"] > progression["stage"]:
                progression["stage"] = event["stage"]
                progression["changes"].append({"at": event["at"], "kind": "advance", "stage": event["stage"]})
                state["observations"].append(event["manifestation"])
            elif progression["arrested"]:
                state["observations"].append("The changes previously recorded appear to have stabilized for now.")
        if all(flag in state["flags"] for flag in event.get("visible_requires", [])):
            state["observations"].append(event["observation"])

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
    if "progression" in state:
        self_preserved = max(10, self_preserved - 12 * (state["progression"]["stage"] - 1))
    contained = min(100, 10 + 18 * state["containment"])
    return {"Truth Preserved": truth / 10, "Self Preserved": self_preserved / 10,
            "Horror Contained": contained / 10}

def apply_memory(state, event, memory):
    """Enrich a committed Inspiration's wording, never its mechanics.

    Only the latest Turn's already-triggered Inspiration is eligible.
    Wording is untrusted narrative input, not a source of new facts.
    """
    if not isinstance(event, str) or not isinstance(memory, str):
        raise ValueError("invalid memory input")
    memory = memory.strip()
    if not 1 <= len(memory) <= 280 or any(ord(ch) < 32 or ord(ch) == 127 for ch in memory):
        raise ValueError("memory must be one short printable paragraph")
    pc = state["dxd"]
    found = [x for x in pc["inspirations"] if x["turn"] == state["turn"] and x["action"] == event]
    if len(found) != 1 or found[0]["source"] != "authored":
        raise ValueError("no eligible unedited Inspiration")
    found[0]["memory"] = memory
    found[0]["source"] = "model"
    pc["memory_edits"].append({"turn": state["turn"], "event": event, "memory": memory})

def verify(state):
    replay = initial(state["scenario"], state["seed"])
    edits = state["dxd"]["memory_edits"]
    cursor = 0
    for action in state["history"]:
        replay = step(replay, action)
        while cursor < len(edits) and edits[cursor]["turn"] == replay["turn"]:
            e = edits[cursor]
            apply_memory(replay, e["event"], e["memory"])
            cursor += 1
    if cursor != len(edits) or replay != state:
        raise ValueError("session replay mismatch")

def view(state):
    _, rules = load(state["scenario"])
    scene = rules.get("scene")
    scene_view = {} if not scene else {"scene": {"description": scene["locations"].get(state["location"], ""),
        "pressure": [p["text"] for p in scene.get("pressure", []) if p["flag"] in state["flags"]],
        "cues": [a["label"] for a in options(state, rules) if a.get("location", state["location"]) == state["location"]]}}
    return scene_view | {k: state[k] for k in ("scenario","time","location","turn","discoveries","observations","ending","last_result")} | {
        "inventory": [item for item in state["inventory"] if not item.startswith(("$", "Flask"))],
        "resources": state["resources"],
        "setting": rules.get("setting", "Fear!"),
        "memories": [x["memory"] for x in state.get("dxd", {}).get("inspirations", [])],
        "memory_prompt": next(({"event": x["action"], "basis": x["basis"]}
            for x in state["dxd"]["inspirations"] if x["turn"] == state["turn"]
            and x["source"] == "authored"), None),
        "contacts": [{"name": p["name"], "role": p["public_role"],
                      **({"demeanor": DEMEANORS[state["relationships"][nid] + 6]} if rules.get("demeanor") else {}),
                      "encounters": p["encounters"], "last_contact": p["last_contact"]}
                     for nid, p in state["npcs"].items() if p["encounters"]],
        "condition": dict(dxd_conditions.describe(state["dxd"]["concerns"]),
                          fear=dxd_morale.describe(state["dxd"]["morale"])),
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

def enrich_memory(path, event, memory, revision):
    state = read(path)
    verify(state)
    if digest(state) != revision:
        raise ValueError("stale session revision")
    apply_memory(state, event, memory)
    verify(state)
    save(path, state)
    return view(state)
