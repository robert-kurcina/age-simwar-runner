"""Bounded, replayable investigation trial. Not the full AIMythos ruleset."""
import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from age_runtime.core.runner import save
from age_runtime.mythos import spatial, pacing, events as narrative_events, proposals, beats, continuity, nominations, hooks
from age_runtime.core import dxd, dxd_conditions, dxd_inspiration, dxd_character, dxd_modifiers, dxd_morale, dxd_psychology, dxd_commitment, dxd_context, dxd_progression

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
        if a.get("location") not in rules["npcs"][a["npc"]].get("eligible_locations", [p["location"]]):
            raise ValueError("NPC interaction location mismatch")
        if "disclosure" in a and (a["disclosure"] not in p["known_topics"]
                                 or a["disclosure"] not in a.get("grant", [])):
            raise ValueError("NPC disclosure must be known and granted")
    if "spatial" in rules:
        for nid, cfg in rules["npcs"].items():
            allowed = cfg.get("eligible_locations", [cfg["location"]])
            if not allowed or any(x not in rules["spatial"]["nodes"] for x in allowed) or (cfg["location"] is not None and cfg["location"] not in allowed):
                raise ValueError("invalid NPC spatial eligibility")
    return profiles

def initial(sid, seed):
    story, rules = load(sid)
    continuity.validate(rules)
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
    if rules.get("local_proposals"):
        state["local_records"] = []
    if "character_profiles" in rules["dxd"]:
        profiles = rules["dxd"]["character_profiles"]
        if set(profiles) != {"pc", *rules["dxd"]["body_profiles"].keys()}:
            raise ValueError("character profile coverage mismatch")
        state["character_profiles"] = copy.deepcopy(profiles)
        if "professional_progression" in rules["dxd"]:
            careers = rules["dxd"]["professional_progression"]["careers"]
            for profile in state["character_profiles"].values():
                profile["proficiencies"]["qualification"] = dxd_progression.describe(profile, careers)
                im = rules["dxd"]["professional_progression"].get("skill_im")
                if im is not None:
                    profile["proficiencies"]["progression"]["fast_track_audit"] = dxd_progression.audit_skills(profile, im)
    if "pacing" in rules:
        state["pacing"] = pacing.initial(rules["pacing"], rules["scene"], state["location"])
    if "spatial" in rules:
        spatial.validate(rules["spatial"], rules["locations"])
        state["transitions"] = []
    if rules.get("demeanor"):
        state["relationship_changes"] = []
    if rules.get("opposition"):
        state["opposition"] = {"marks": 0, "resolved": False}
    if "event_clocks" in rules or "encounter_table" in rules:
        state["narrative_events"] = narrative_events.initial(rules)
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
        if rules.get("emotional_commitment"):
            state["dxd"]["commitments"] = []
        if "character_profiles" in state:
            state["dxd"]["concerns"]["capacity"]["resilience"] += state["dxd"]["skills"].get("Grit", 0)
            if rules.get("native_disabilities"):
                dxd_context.initialize(state)
        if "activity" in rules:
            state["dxd"]["activity"] = dxd_conditions.activity_initial(derived["pc"]["attributes"], rules["activity"]["initial_awake_seconds"])
        for nid, profile in state["npcs"].items():
            profile["dxd_attributes"] = derived[nid]["attributes"]
            profile["body"] = derived[nid]
            if "character_profiles" in state:
                profile["skills"] = copy.deepcopy(state["character_profiles"][nid]["proficiencies"]["skills"])
                profile["dxd_traits"] = copy.deepcopy(state["character_profiles"][nid]["proficiencies"]["traits"])
    return state

def npc_available(state, rules, action):
    if "npc" not in action:
        return True
    nid = action["npc"]
    npc = state["npcs"][nid]
    cfg = rules["npcs"][nid]
    destination = action.get("location")
    return (not continuity.blocked(state, cfg)
            and all(f in state["flags"] for f in cfg.get("requires_flags", []))
            and destination in cfg.get("eligible_locations", [npc["location"]])
            and (npc["location"] is None or npc["location"] == destination))

def spatial_options(state, rules, candidates):
    config = rules["spatial"]
    now = datetime.fromisoformat(state["time"])
    result = []
    for action in candidates:
        destination = action.get("location", state["location"])
        trip = spatial.route(config, state["location"], destination, state["time"], state["flags"])
        if trip is None:
            continue
        local = action["duration_seconds"] - trip["seconds"] if "until" in action else action["duration_seconds"]
        if local <= 0:
            continue
        arrival = now + timedelta(seconds=trip["seconds"])
        finish = arrival + timedelta(seconds=local)
        if action.get("available_from") and arrival < datetime.fromisoformat(action["available_from"]):
            continue
        if action.get("available_until") and finish > datetime.fromisoformat(action["available_until"]):
            continue
        result.append(dict(action, duration_seconds=trip["seconds"] + local, local_seconds=local, route=trip))
    for trip in spatial.reachable(config, state):
        result.append({"id": "move:" + trip["destination"], "label": "Go to " + trip["destination"],
                       "location": trip["destination"], "duration_seconds": trip["seconds"], "local_seconds": 0,
                       "interval_seconds": 60 if trip["seconds"] <= 360 else 600 if trip["seconds"] <= 3600 else 3600,
                       "route": {k: v for k, v in trip.items() if k != "destination"}, "repeatable": True})
    return result

def options(state, rules):
    if state["ending"]:
        return []
    clock = state["dxd"].get("activity")
    if clock and clock["status"] == "asleep":
        remaining = int((datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds())
        if remaining <= 0:
            return []
        duration = min(remaining, max(60, clock["required_sleep_seconds"] - clock["sleep_seconds"]))
        result = [{"id": "continue_sleep", "label": "Continue sleeping", "location": state["location"],
                   "duration_seconds": duration, "local_seconds": duration, "activity": "sleep",
                   "interval_seconds": 3600, "repeatable": True, "route": {"nodes": [state["location"]], "seconds": 0, "minutes": 0, "terrain": []}}]
        if clock["sleep_seconds"] >= 3600 and remaining >= 60:
            result.append(dict(result[0], id="wake_early", label="Attempt to wake early", duration_seconds=60,
                               local_seconds=60, interval_seconds=60))
        return result
    candidates = [a for a in rules["actions"] if (a.get("repeatable") or a["id"] not in state["used"])
                  and len(state["discoveries"]) >= a.get("requires", 0)
                  and all(f in state["flags"] for f in a.get("requires_flags", []))
                  and (not a.get("requires_any_flags") or any(f in state["flags"] for f in a["requires_any_flags"]))
                  and all(f in state["used"] for f in a.get("requires_used", []))
                  and not any(f in state["flags"] for f in a.get("excludes_flags", []))
                  and all(state["relationships"][k] >= v for k, v in a.get("requires_relationship", {}).items())
                  and npc_available(state, rules, a)
                  and continuity.reconsideration_allowed(state, a)
                  and ("spatial" in rules or not a.get("available_from") or state["time"] >= a["available_from"])
                  and (not a.get("available_until") or state["time"] < a["available_until"])
                  and ("disclosure" not in a or a["disclosure"] not in state["npcs"][a["npc"]]["disclosed"])] + [
                      {"id":"observe", "label":"Spend time observing the surroundings", "location":state["location"], "minutes":rules.get("observe_minutes", 30)}]
    if clock and state["location"] == rules["activity"]["sleep_location"]:
        available = int((datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds())
        duration = min(available, dxd_conditions.required_sleep(state["dxd"]["concerns"], state["dxd"]["attributes"]))
        if duration > 0:
            candidates.append({"id": "sleep_room", "label": "Sleep at the boarding house",
                               "location": state["location"], "seconds": duration, "activity": "sleep",
                               "interval_seconds": 3600, "repeatable": True,
                               "cost": {"cash_cents": rules["activity"]["sleep_cost_cents"]}})
    timed = []
    for a in candidates:
        seconds = int((datetime.fromisoformat(a["until"]) - datetime.fromisoformat(state["time"])).total_seconds()) if "until" in a else pacing.duration(a)
        seconds, saved = proposals.prepared_duration(state, a, seconds)
        timed.append(dict(a, duration_seconds=seconds, **({"preparation_saved_seconds": saved} if saved else {})))
    candidates = timed
    if "spatial" in rules:
        candidates = spatial_options(state, rules, candidates)
    remaining = (datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds()
    return [a for a in candidates if 0 < a["duration_seconds"] <= remaining
            and (not a.get("available_until") or datetime.fromisoformat(state["time"]) + timedelta(seconds=a["duration_seconds"]) <= datetime.fromisoformat(a["available_until"]))
            and all(state["resources"][k] >= v for k, v in a.get("cost", {}).items())]

def resolve_dxd(state, rules, action):
    """Gather only authored applicable modifiers and allocate Favor before rolling."""
    spec = copy.deepcopy(action["test"])
    interaction = spec.get("interaction")
    if interaction:
        if spec["attribute"] != "PRE" or interaction not in ("ordinary", "pivotal") or action.get("npc") not in state["npcs"]:
            raise ValueError("invalid Interaction Test")
        if dxd.attribute_dm(state["dxd"]["attributes"]["INT"]) >= 2:
            spec["additional_attributes"] = ["INT"]
    cfg = rules["dxd"]
    pc = state["dxd"]
    if "character_profiles" in state and spec.get("morale_event") and "Grit" in pc["skills"]:
        spec["skill"] = "Grit"
    gathered = dxd_modifiers.gather(pc["attributes"], pc["skills"], pc["traits"], spec)
    attr = sum(x["dm"] for x in gathered["attribute"])
    skill = sum(x["dm"] for x in gathered["skill"])
    other = [x["dm"] for key in ("trait", "explicit", "interdisciplinary") for x in gathered[key]]
    contextual, context_dm, emotional_triggers = dxd_context.effects(state, action, spec)
    mods = dxd_modifiers.totals(gathered)
    condition = dxd_conditions.penalty_dice(pc["concerns"], decision=spec.get("decision", False))
    hook = (dxd_commitment.effective_demeanor(state, action.get("npc"), action) if rules.get("demeanor") and spec["attribute"] == "PRE"
            else 1 if spec.get("relationship_bonus") and state["relationships"][spec["relationship_bonus"]] >= 1 else 0)
    cue = spec.get("inspiration")
    inspiration_dm = dxd_inspiration.applicable_dm(pc["inspirations"], [cue["tag"]] if cue else [])
    policy = cfg["favor"]
    emicted = dxd.emicted_favor(available=pc["favor"], maximum=policy["maximum"],
                                 enabled=policy.get("emicted", False))
    psychology = dxd_psychology.effects(pc["morale"], spec.get("psychology_context"))
    progression_dm = -(state["progression"]["stage"] - 1) if "progression" in state and spec["attribute"] == "POW" else 0
    emotional_dm = dxd_commitment.modifier(pc, action)
    leverage_dm = dxd_commitment.leverage(state, action)
    character_hook_dm = action.get("character_hook", {}).get("dm", 0)
    components = [character_hook_dm, context_dm, emotional_dm, -leverage_dm if interaction != "pivotal" else 0, attr, skill, hook, inspiration_dm, emicted, spec.get("fixed_dm", 0), psychology["dm"], progression_dm] + other
    favor = dxd.automatic_favor(available=pc["favor"], maximum=policy["maximum"],
                                significance=spec["significance"], desired=policy["desired"])
    net = mods["bonus"] - mods["penalty"] - condition - psychology["penalty"] - sum(x["penalty"] for x in contextual)
    bonus = min(policy["maximum"], max(0, net))
    penalty = max(0, -net)
    args = {"favor": favor, "bonus": bonus}
    npc_gathered = None
    if interaction == "pivotal":
        npc = state["npcs"][action["npc"]]
        npc_attrs = npc["dxd_attributes"]
        target_spec = {"attribute": "INT", **spec.get("opposition", {})}
        npc_gathered = dxd_modifiers.gather(npc_attrs, npc.get("skills", {}), npc.get("dxd_traits", {}), target_spec, player=False)
        target_mods = dxd_modifiers.totals(npc_gathered)
        # NPCs do not receive the PC-only additional Attribute bonus.
        args = {"active_raw": pc["attributes"]["PRE"], "target_raw": npc_attrs["INT"],
                "active_dm": sum(components) - dxd.attribute_dm(pc["attributes"]["PRE"]),
                "active_bonus": bonus, "active_penalty": penalty, "active_favor": favor,
                "target_dm": target_mods["dm"] - dxd.attribute_dm(npc_attrs["INT"]) + leverage_dm,
                "target_bonus": target_mods["bonus"], "target_penalty": target_mods["penalty"]}
    elif spec.get("narrative"):
        args.update(narrative=True, tn=spec["tn"], dm=sum(max(0, x) for x in components),
                    adversity=sum(max(0, -x) for x in components), adversity_dice=penalty)
    elif "npc_attribute" in spec:
        npc = state["npcs"][action["npc"]]
        args.update(narrative=True, dm=sum(max(0, x) for x in components),
                    adversity=sum(max(0, -x) for x in components), adversity_dice=penalty,
                    npc_dm=dxd.attribute_dm(npc["dxd_attributes"][spec["npc_attribute"]])
                           + spec.get("npc_adversity", 0))
    else:
        args.update(tn=spec["tn"], dm=sum(components), penalty=penalty)
    pc["favor"] -= favor
    chance = dxd_inspiration.opposed_probability(**args) if interaction == "pivotal" else dxd_inspiration.probability(**args)
    seed_parts = [state["seed"], state["turn"]]
    if spec.get("morale_event"):
        seed_parts.append(spec["morale_event"])
    first = (dxd.opposed if interaction == "pivotal" else dxd.test)(digest(seed_parts), **args)
    result = first
    inspired = None
    if (interaction != "pivotal" and not first["passed"] and cue and cfg.get("inspiration", {}).get("enabled")
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
    dxd_context.record(state, emotional_triggers, result)
    pc["tests"].append({"turn": state["turn"], "action": action["id"],
                        "inputs": args, "components": {"attribute": attr, "skill": skill,
                        "condition_penalty_dice": condition, "relationship": hook,
                        **({"emotional_commitment": emotional_dm, "commitment_leverage": leverage_dm} if "commitments" in pc else {}),
                        "inspiration": inspiration_dm, "emicted": emicted, "psychology": psychology, "progression": progression_dm},
                        "gathered": gathered, **({"character_hook": copy.deepcopy(action["character_hook"])} if "character_hook" in action else {}), **({"contextual": contextual, "npc_gathered": npc_gathered} if "character_profiles" in state else {}), "net_bonus": bonus, "net_penalty": penalty,
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
        dxd_commitment.supersede_demeanor(state, key)
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

def activity_segment(state, rules, seconds, mode, *, safe=False, interruptible=False):
    """Apply recovery and events in chronological order, stopping at explicit interruptions."""
    pc = state["dxd"]
    clock = pc["activity"]
    start = datetime.fromisoformat(state["time"])
    finish = start + timedelta(seconds=seconds)
    cursor = start
    events = sorted((e for e in rules.get("events", []) if e["id"] not in state["events_seen"]
                     and start < datetime.fromisoformat(e["at"]) <= finish), key=lambda e: e["at"])
    boundaries = sorted(set([finish] + [datetime.fromisoformat(e["at"]) for e in events]))
    reason = None
    while cursor < finish:
        boundary = next(b for b in boundaries if b > cursor)
        if "narrative_events" in state:
            interval = narrative_events.next_boundary(state, rules)
            if interval is not None:
                boundary = min(boundary, cursor + timedelta(seconds=interval))
        span = int((boundary - cursor).total_seconds())
        before = dxd_conditions.degrees(pc["concerns"])["stress"]
        actual = dxd_conditions.advance_activity(pc["concerns"], clock, span, mode, safe=safe,
                                                 seed=state["seed"], attributes=pc["attributes"])
        dxd_morale.calm(pc["morale"], safe=safe, stress_degrees_removed=before - dxd_conditions.degrees(pc["concerns"])["stress"])
        cursor += timedelta(seconds=actual)
        state["time"] = cursor.isoformat()
        narrative_events.advance_time(state, rules, actual)
        advance_events(state, rules, cursor)
        if mode != "sleep" and clock["pending_sleep_seconds"] == 0:
            dxd_conditions.begin_sleep(pc["concerns"], clock, pc["attributes"])
            reason = "involuntary_sleep"
            break
        if interruptible and any(e.get("interrupt_activity") and datetime.fromisoformat(e["at"]) == cursor
                                 and (not e.get("locations") or state["location"] in e["locations"]) for e in events):
            reason = "event"
            break
    return reason

def history_entry(action, proposal, commitment):
    if commitment is not None:
        return {"action": action, "proposal": copy.deepcopy(proposal), "commitment": copy.deepcopy(commitment)}
    return action if proposal is None else {"proposal": copy.deepcopy(proposal)}

def finish_activity(state, rules, action, a, success, reason=None, proposal=None):
    state["last_result"] = {"action": action, "success": success}
    if reason:
        state["last_result"]["interrupted"] = reason
    if state["transitions"] and state["transitions"][-1]["turn"] == state["turn"]:
        state["last_result"]["transition"] = state["transitions"][-1]
    if "activity" in state["dxd"]:
        pc = state["dxd"]
        dxd_conditions.refresh_sleep_limit(pc["concerns"], pc["activity"], pc["attributes"])
    pacing.reconcile_scene(state, rules)
    pacing.record(state, a)
    state["history"].append(history_entry(action, proposal, a.get("commitment")))
    if not options(state, rules):
        state["ending"] = {"reason": "limit", "evidence_count": len(state["discoveries"]),
                           **{key: flag in state["flags"] for key, flag in rules.get("ending_flags", {
                               "account_prepared": "written_account", "account_relayed": "account_relayed",
                               "account_entrusted": "account_entrusted"}).items()},
                           "epilogue": rules["ending_text"]["limit"], "scores": scores(state, action)}
    return state

def step(state, action, proposal=None, commitment=None):
    state = copy.deepcopy(state)
    _, rules = load(state["scenario"])
    request, _ = hooks.split(proposal)
    request, nomination = nominations.split(request)
    a = next((a for a in options(state, rules) if a["id"] == action), None)
    if request is not None and action.startswith("beat:"):
        a = beats.compile_beat(state, rules, request)
    elif request is not None and action.startswith("local:"):
        a = proposals.compile_local(state, rules, request, npc_available)
    elif a is None:
        raise ValueError("action unavailable")
    elif request is not None:
        a = proposals.compile_action(state, rules, request, [a])
        if a["id"] != action:
            raise ValueError("proposal action mismatch")
    if a["id"] != action:
        raise ValueError("proposal action mismatch")
    a = nominations.apply(state, rules, a, nomination)
    if commitment is not None:
        dxd_commitment.validate(state, rules, a, commitment)
        a = dict(a, commitment=copy.deepcopy(commitment))
    elapsed = datetime.fromisoformat(state["time"]) + timedelta(seconds=a["duration_seconds"])
    if elapsed > datetime.fromisoformat(rules["end"]):
        raise ValueError("action exceeds scenario deadline")
    state["turn"] += 1
    clock = state["dxd"].get("activity")
    if "spatial" in rules and a["route"]["seconds"]:
        departure = state["time"]
        arrival = datetime.fromisoformat(departure) + timedelta(seconds=a["route"]["seconds"])
        if clock:
            reason = activity_segment(state, rules, a["route"]["seconds"], "travel")
            if reason:
                # No partial edge position is modeled: retain the last anchored node.
                return finish_activity(state, rules, action, a, False, reason, proposal)
        else:
            advance_events(state, rules, arrival)
        state["transitions"].append({"turn": state["turn"], "start": departure, "arrival": arrival.isoformat(), **a["route"]})
    state["location"] = a.get("location", state["location"])
    if clock:
        # Events during travel may invalidate the intended local action.
        if (any(f in state["flags"] for f in a.get("excludes_flags", []))
                or not all(f in state["flags"] for f in a.get("requires_flags", []))
                or not npc_available(state, rules, a)):
            return finish_activity(state, rules, action, a, False, "availability_changed", proposal)
        mode = a.get("activity", "active")
        if action == "sleep_room":
            for key, amount in a.get("cost", {}).items():
                state["resources"][key] -= amount
            dxd_conditions.begin_sleep(state["dxd"]["concerns"], clock, state["dxd"]["attributes"])
        elif a.get("cost"):
            for key, amount in a["cost"].items():
                state["resources"][key] -= amount
        reason = activity_segment(state, rules, a.get("local_seconds", a["duration_seconds"]), mode,
                                  safe=a.get("safe", False), interruptible=mode in ("rest", "low_energy", "sleep", "restorative", "quiet"))
        if mode == "sleep":
            pc = state["dxd"]
            before = dxd_conditions.degrees(pc["concerns"])["stress"]
            woke = False
            if (action == "wake_early" and not reason) or clock["sleep_seconds"] >= clock["required_sleep_seconds"]:
                woke = dxd_conditions.wake(pc["concerns"], clock, pc["attributes"], seed=state["seed"],
                                          forced=action == "wake_early")
            dxd_morale.calm(pc["morale"], safe=False, stress_degrees_removed=before - dxd_conditions.degrees(pc["concerns"])["stress"])
            return finish_activity(state, rules, action, a, woke if action == "wake_early" else not bool(reason), reason)
        if reason:
            return finish_activity(state, rules, action, a, False, reason, proposal)
        if (any(f in state["flags"] for f in a.get("excludes_flags", []))
                or not all(f in state["flags"] for f in a.get("requires_flags", []))
                or not npc_available(state, rules, a)):
            return finish_activity(state, rules, action, a, False, "availability_changed", proposal)
    else:
        if "progression" in state or "pacing" in rules:
            advance_events(state, rules, elapsed)
        state["time"] = elapsed.isoformat()
    if action != "observe" and not a.get("repeatable"):
        state["used"].append(action)
    if not clock:
        for key, amount in a.get("cost", {}).items():
            state["resources"][key] -= amount
    npc = state["npcs"].get(a.get("npc"))
    if npc is not None:
        if npc["location"] is None:
            npc["location"] = state["location"]
        npc["encounters"] += 1
        npc["last_contact"] = state["time"]
    success = True
    if "test" in a:
        pacing.reconcile_scene(state, rules)
        a = hooks.apply(state, rules, a)
        success = resolve_dxd(state, rules, a)
    primary_result = state["dxd"]["tests"][-1]["result"] if "test" in a else None
    if primary_result is not None and not success:
        continuity.record_refusal(state, a, state["dxd"]["tests"][-1])
    if primary_result is not None and rules.get("automatic_emphasis"):
        hooks.record(state, a, state["dxd"]["tests"][-1])
    if commitment is not None:
        entry = dxd_commitment.record(state, a, primary_result)
        dxd_context.acquire_commitment_disability(state["dxd"], entry)
    if a.get("test", {}).get("interaction"):
        # Signed margin is the Test Effect; ordinary Demeanor limits still apply.
        change_demeanor(state, a["npc"], primary_result["margin"])
        if commitment is not None:
            entry["demeanor_at_commitment"] = state["relationships"][a["npc"]]
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
        if not clock:
            dxd_conditions.recover(concerns, a.get("local_seconds", a["duration_seconds"]) // 60, **a.get("recovery", {}))
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
                event=spec["morale_event"], turn=state["turn"],
                grit=state["dxd"]["skills"].get("Grit", 0))
            if not reaction["passed"]:
                state["observations"].append(hazard["reaction"])
                if "cosmic_failure" in hazard:
                    revelation = hazard["cosmic_failure"]
                    dxd_psychology.acquire(state["dxd"]["morale"], concerns,
                        revelation=revelation["revelation"], understood=True, destabilized=True,
                        disability=revelation["disability"], turn=state["turn"])
    if "progression" not in state and "pacing" not in rules:
        advance_events(state, rules, elapsed)
    if a.get("danger_beat"):
        beats.record(state, rules, a, primary_result)
    if a.get("local_capability"):
        proposals.record_local(state, a, success, primary_result)
    narrative_events.complete_action(state, rules, a, success, a.get("local_seconds", a["duration_seconds"]))
    if clock:
        dxd_conditions.refresh_sleep_limit(state["dxd"]["concerns"], clock, state["dxd"]["attributes"])
    state["last_result"] = {"action": action, "success": success}
    if a.get("preparation_saved_seconds"):
        state["last_result"]["preparation_saved_seconds"] = a["preparation_saved_seconds"]
    if proposal is not None:
        result = primary_result
        state["last_result"]["adjudication"] = {k: result[k] for k in ("passed", "dos", "dof", "margin")}
        state["last_result"]["approach"] = proposal["approach"]
    if "spatial" in rules and a["route"]["seconds"]:
        state["last_result"]["transition"] = state["transitions"][-1]
    if npc is not None:
        state["last_result"]["participant"] = npc["name"]
    pacing.reconcile_scene(state, rules)
    pacing.record(state, a)
    state["history"].append(history_entry(action, proposal, a.get("commitment")))
    terminal = a.get("terminal") and (success or not a.get("terminal_on_success"))
    if terminal or ("pacing" not in rules and state["turn"] >= rules["max_turns"]) or not options(state, rules):
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

def narrative_step(state, request):
    result = copy.deepcopy(state)
    _, rules = load(result["scenario"])
    pacing.control(result, rules, request)
    result["history"].append({"narrative": copy.deepcopy(request)})
    return result

def narrative(path, request, revision):
    state = read(path)
    verify(state)
    if digest(state) != revision:
        raise ValueError("stale session revision")
    state = narrative_step(state, request)
    verify(state)
    save(path, state)
    return view(state)

def verify(state):
    replay = initial(state["scenario"], state["seed"])
    edits = state["dxd"]["memory_edits"]
    cursor = 0
    for entry in state["history"]:
        if isinstance(entry, dict) and "narrative" in entry:
            replay = narrative_step(replay, entry["narrative"])
            continue
        if isinstance(entry, dict) and "commitment" in entry:
            replay = step(replay, entry["action"], entry.get("proposal"), entry["commitment"])
        else:
            replay = step(replay, entry["proposal"]["action"], entry["proposal"]) if isinstance(entry, dict) else step(replay, entry)
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
    if scene and "spatial" in rules:
        config = rules["spatial"]
        scene_view["scene"]["zone"] = config["nodes"][state["location"]]["zone"]
        scene_view["scene"]["routes"] = [r for r in spatial.reachable(config, state) if r["seconds"] <= (datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds()] if not state["ending"] else []
        scene_view["scene"]["contacts_here"] = [p["name"] for nid, p in state["npcs"].items() if p["encounters"] and p["location"] == state["location"] and npc_available(state, rules, {"npc": nid, "location": state["location"]})]
    if "pacing" in state:
        scene_view["pacing"] = pacing.projection(state, rules)
    if rules.get("danger_beats"):
        scene_view["danger"] = beats.available(state, rules)
    if "commitments" in state["dxd"]:
        scene_view["emotional_commitments"] = copy.deepcopy(state["dxd"]["commitments"])
    if "local_records" in state:
        scene_view["local_records"] = copy.deepcopy(state["local_records"][-8:])
    if "narrative_events" in state:
        scene_view["event_pressure"] = narrative_events.projection(state, rules)
    if "activity" in state["dxd"]:
        clock = state["dxd"]["activity"]
        scene_view["activity"] = {k: clock[k] for k in ("status", "awake_seconds", "limit_seconds", "overdue_seconds", "sleep_seconds", "required_sleep_seconds", "activity", "pending_sleep_seconds")}
    if rules.get("automatic_emphasis"):
        scene_view["character_emphasis_xp"] = state["dxd"].get("xp", 0)
        scene_view["latest_emphasis_award"] = next((copy.deepcopy(e) for e in reversed(state["dxd"].get("emphasis_awards", [])) if e["turn"] == state["turn"]), None)
    return scene_view | {k: state[k] for k in ("scenario","time","location","turn","discoveries","observations","ending","last_result")} | {
        "inventory": [item for item in state["inventory"] if not item.startswith(("$", "Flask"))],
        "resources": state["resources"],
        "setting": rules.get("setting", "Fear!"),
        "memories": [x["memory"] for x in state.get("dxd", {}).get("inspirations", [])],
        "memory_prompt": next(({"event": x["action"], "basis": x["basis"]}
            for x in state["dxd"]["inspirations"] if x["turn"] == state["turn"]
            and x["source"] == "authored"), None),
        "contacts": [{"name": p["name"], "role": p["public_role"],
                      **({"demeanor": DEMEANORS[dxd_commitment.effective_demeanor(state, nid) + 6]} if rules.get("demeanor") else {}),
                      "encounters": p["encounters"], "last_contact": p["last_contact"]}
                     for nid, p in state["npcs"].items() if p["encounters"]],
        "condition": dict(dxd_conditions.describe(state["dxd"]["concerns"]),
                          fear=dxd_morale.describe(state["dxd"]["morale"])),
        "revision": digest(state), "opening": rules["opening"] if not state["turn"] else None,
        "choices": [{"id": a["id"], "label": a["label"], **({"minutes": a["duration_seconds"] / 60, "seconds": a["duration_seconds"], "destination": a.get("location", state["location"]), "travel_minutes": a["route"]["minutes"], "travel_seconds": a["route"]["seconds"]} if "spatial" in rules else {}), **({"preparation_saved_seconds": a["preparation_saved_seconds"]} if a.get("preparation_saved_seconds") else {})} for a in options(state, rules)]}

def gm_context(state):
    """Bounded referee packet; never render directly as player narration."""
    story, rules = load(state["scenario"])
    if not rules.get("gm_proposals"):
        raise ValueError("GM context not yet supported for scenario")
    public = view(state)
    # Keep complete authoritative history in the checkpoint, not every prompt.
    recent = {k: public[k] for k in ("scenario", "time", "location", "turn",
              "ending", "last_result", "condition", "resources", "revision", "choices")}
    recent.update({k: public[k] for k in ("scene", "pacing", "activity", "event_pressure", "local_records", "danger", "emotional_commitments") if k in public})
    recent["observations"] = state["observations"][-8:]
    recent["discoveries"] = list(state["discoveries"])
    recent["contacts"] = public["contacts"]
    recent["inventory"] = public["inventory"]
    recent["memories"] = public["memories"][-4:]
    recent["memory_prompt"] = public["memory_prompt"]
    recent["opening"] = public["opening"]
    if "pacing" in recent and recent["pacing"]["current_spotlight"]:
        active = copy.deepcopy(recent["pacing"]["current_spotlight"])
        active["activities"] = active["activities"][-6:]
        recent["pacing"]["current_spotlight"] = active
    pc = state["dxd"]
    legal = options(state, rules)
    local = [a for a in legal if a.get("location", state["location"]) == state["location"]]
    relevant = {a["npc"] for a in local if "npc" in a}
    return {"audience": "gm_only", "source_revision": state["source"],
            "player_surface": recent,
            "referee": {
                "location_basis": next(({"features": x["features"], "dangers": x["dangers"]}
                    for x in story["locations"] if x["name"] == state["location"]), None),
                "participants": [{"id": key, "name": state["npcs"][key]["name"],
                                  "motivation": state["npcs"][key]["motivation"],
                                  "known_topics": state["npcs"][key]["known_topics"],
                                  "disclosed": state["npcs"][key]["disclosed"],
                                  "secret": state["npcs"][key]["secret"],
                                  "location": state["npcs"][key]["location"],
                                  "skills": copy.deepcopy(state["npcs"][key].get("skills", {})),
                                  "traits": copy.deepcopy(state["npcs"][key].get("dxd_traits", {}))}
                                 for key in sorted(relevant)],
                "concerns": copy.deepcopy(pc["concerns"]),
                "attributes": dict(pc["attributes"]), "skills": copy.deepcopy(pc["skills"]),
                "traits": copy.deepcopy(pc["traits"]),
                "character_profile": copy.deepcopy(state.get("character_profiles", {}).get("pc")),
                "addiction_check": copy.deepcopy(pc.get("addiction_check")),
                "addicted": pc.get("addicted", False),
                "favor": pc["favor"],
                "commitment_options": [{"action": a["id"], "context": a["npc"], "level": 1} for a in legal if dxd_commitment.eligible(state, rules, a)],
                "modifier_nominations": nominations.projection(state, rules, legal, npc_available),
                "character_hooks": {a["id"]: h for a in legal if (h := hooks.offers(state, rules, a))},
                "persistent_circumstances": {a["id"]: h for a in legal if (h := hooks.circumstances(state, rules, a))},
                "character_emphasis_xp": pc.get("xp", 0),
                "narrative_functions": continuity.projection(state, rules, legal),
                "local_capabilities": proposals.local_capabilities(state, rules, npc_available),
                "approaches": {a["id"]: sorted(rules["gm_proposals"][a["id"]])
                               for a in legal if a["id"] in rules.get("gm_proposals", {})},
                "clocks": [{"id": key, "name": cfg["name"], "source": cfg["source"],
                            "segments": cfg["segments"], **state["narrative_events"]["clocks"][key]}
                           for key, cfg in rules.get("event_clocks", {}).items()
                           if not state["narrative_events"]["clocks"][key]["resolved"]],
                "last_test": {k: pc["tests"][-1]["result"][k] for k in ("passed", "margin", "dos", "dof")}
                             if pc["tests"] and pc["tests"][-1]["turn"] == state["turn"] else None}}

def inspect_gm(path):
    state = read(path)
    verify(state)
    return gm_context(state)

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

def act(path, action, revision, proposal=None, commitment=None):
    state = read(path)
    verify(state)
    if digest(state) != revision:
        raise ValueError("stale session revision")
    state = step(state, action, proposal, commitment)
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
