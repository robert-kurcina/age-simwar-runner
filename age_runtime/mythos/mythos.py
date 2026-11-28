"""Bounded, replayable investigation trial. Not the full AIMythos ruleset."""
import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from age_runtime.core import opportunity_latitude as latitude
from age_runtime.core.runner import save
from age_runtime.mythos import projections, resolution, npc_agenda, settlement_activity, incidental_people
from age_runtime.mythos import spatial, pacing, events as narrative_events, proposals, beats, continuity, nominations, hooks, epistemic, establishment, agreements, locks, timed_details, emotions, reminders, npc_time, action_observations, behavior, expectations, npc_travel, npc_agency, medical
from age_runtime.core import dxd, dxd_conditions, dxd_inspiration, dxd_character, dxd_modifiers, dxd_morale, dxd_psychology, dxd_commitment, dxd_context, dxd_progression, dxd_injury, dxd_hitpoints

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

def initial(sid, seed, opportunity_latitude=None):
    story, rules = load(sid)
    level = latitude.select(rules.get("opportunity_latitude", latitude.DEFAULT), opportunity_latitude)
    return _initial(sid, seed, story, rules, opportunity_latitude=level)


def _initial(sid, seed, story, rules, *, opportunity_latitude=None):
    latitude.validate(rules.get("opportunity_latitude", latitude.DEFAULT))
    continuity.validate(rules)
    epistemic.validate_propositions(rules)
    proposals.validate_local(rules)
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
    if opportunity_latitude is not None:
        state["opportunity_latitude"] = latitude.validate(opportunity_latitude)
        state["settings_digest"] = digest([state["source"], seed, opportunity_latitude])
    if rules.get("epistemic_dialogue"):
        state["dialogue"] = []
    if rules.get("social_epistemic"):
        state["dynamic_propositions"] = {}
        state["belief_revisions"] = []
    if rules.get("narrative_establishment"):
        state["established_details"] = []
    if rules.get("incidental_people"):
        if not rules.get("narrative_establishment"):
            raise ValueError("incidental people require narrative establishment")
        state["incidental_people"] = {}
    if rules.get("narrative_properties"):
        state["detail_changes"] = []
    if rules.get("narrative_custody"):
        state["custody_transfers"] = []
    if rules.get("narrative_agreements"):
        state["agreement_history"] = []
    if rules.get("narrative_locks"):
        state["narrative_locks"] = []
    if rules.get("interpersonal_duress"):
        state["emotional_episodes"] = []
    if rules.get("consequential_objects"):
        state["object_actions"] = []
    if rules.get("action_observations"):
        state["action_observations"] = []
    if rules.get("behavioral_recognition"):
        state["behavioral_recognition"] = []
    if rules.get("routine_observations"):
        state["routine_observations"] = []
        state["routine_source"] = None
    if rules.get("npc_expectations"):
        state["npc_expectations"] = []
    if rules.get("npc_travel"):
        state["npc_travel"] = []
    if rules.get("timed_detail_event"):
        state["timed_detail_events"] = []
    if rules.get("medical_bandaging"):
        if not (rules.get("native_injury_lifecycle") and rules.get("timed_detail_event") and rules.get("npc_temporal")):
            raise ValueError("medical bandaging requires injury lifecycle and timed NPC events")
        supplies = rules["medical_bandaging"]["caregivers"]
        if not isinstance(supplies, dict) or set(supplies) - set(state["npcs"]) or any(type(n) is not int or not 0 <= n <= 16 for n in supplies.values()):
            raise ValueError("invalid reviewed medical supplies")
        state["medical_supplies"] = dict(supplies)
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
        if rules.get("native_hitpoints"):
            state["dxd"]["hitpoints"] = dxd_hitpoints.initial(derived["pc"]["physical"]["base_hitpoints"])
        if rules.get("native_injury"):
            state["dxd"]["injury"] = dxd_injury.initial(derived["pc"]["physical"]["bodypoints"],
                                                    *([derived["pc"]["attributes"]["SIZ"], state["dxd"]["concerns"]["capacity"]["recovery_rate"]]
                                                      if rules.get("native_injury_lifecycle") else []))
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
            if rules.get("interpersonal_duress"):
                profile["concerns"] = dxd_conditions.initial(profile["dxd_attributes"])
                profile["concerns"]["capacity"]["resilience"] += profile.get("skills", {}).get("Grit", 0)
    npc_agenda.validate(rules)
    settlement_activity.validate(rules)
    incidental_people.validate(rules)
    npc_time.initialize(state, rules)
    npc_agenda.initialize_presence(state, rules)
    npc_agenda.observe_boundary(state, rules)
    npc_agency.initialize(state, rules)
    return state

def npc_available(state, rules, action):
    if "npc" not in action:
        return True
    nid = action["npc"]
    npc = state["npcs"][nid]
    cfg = rules["npcs"][nid]
    destination = action.get("location")
    return (not npc_travel.pending(state, nid)
            and npc.get("activity", {}).get("status") != "asleep"
            and not continuity.blocked(state, cfg)
            and all(f in state["flags"] for f in cfg.get("requires_flags", []))
            and destination in cfg.get("eligible_locations", [npc["location"]])
            and (npc["location"] is None or npc["location"] == destination))

def _available_local_npcs(state, rules):
    """Anchored NPCs eligible to witness or participate at the PC's location."""
    return {nid for nid, npc in state["npcs"].items()
            if npc["location"] == state["location"]
            and npc_available(state, rules, {"npc": nid, "location": state["location"]})}


def _local_action_available(state, rules, action):
    """Revalidate the same prerequisites at arrival and after local activity."""
    return (not any(f in state["flags"] for f in action.get("excludes_flags", []))
            and all(f in state["flags"] for f in action.get("requires_flags", []))
            and (not action.get("requires_any_flags") or any(f in state["flags"] for f in action["requires_any_flags"]))
            and all(f in state["used"] for f in action.get("requires_used", []))
            and len(state["discoveries"]) >= action.get("requires", 0)
            and all(state["relationships"][k] >= v for k, v in action.get("requires_relationship", {}).items())
            and (not action.get("available_from") or state["time"] >= action["available_from"])
            and (not action.get("available_until") or state["time"] <= action["available_until"])
            and npc_available(state, rules, action)
            and locks.action_available(state, rules, action, npc_available, establishment.local_entities)
            and beats.completion_available(state, rules, action)
            and proposals.completion_available(state, rules, action, npc_available))

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
    injury = state["dxd"].get("injury")
    if dxd_hitpoints.incapacitated(state["dxd"]):
        if injury and dxd_injury.projection(injury)["status"] == "dead":
            return []
        remaining = int((datetime.fromisoformat(rules["end"]) - datetime.fromisoformat(state["time"])).total_seconds())
        duration = min(remaining, dxd_injury.next_boundary(injury) or 600, dxd_hitpoints.awakening_boundary(state["dxd"]) or 600)
        if duration <= 0:
            return []
        return [{"id": "await_assistance", "label": "Advance time while incapacitated", "location": state["location"],
                 "duration_seconds": duration, "local_seconds": duration, "interval_seconds": 60,
                 "repeatable": True, "route": {"nodes": [state["location"]], "seconds": 0, "minutes": 0, "terrain": []}}]
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
            candidates.append({"id": "sleep_room", "label": "Sleep at the boarding house" if rules["activity"]["sleep_location"] == "Sailor's Rest Boarding House" else "Sleep at " + rules["activity"]["sleep_location"],
                               "location": state["location"], "seconds": duration, "activity": "sleep",
                               "interval_seconds": 3600, "repeatable": True,
                               "cost": {"cash_cents": rules["activity"]["sleep_cost_cents"]}})
    candidates += locks.actions(state, rules, npc_available, establishment.local_entities)
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
    """Compatibility entry point for native player Test resolution."""
    return resolution.resolve(state, rules, action, digest)


DEMEANORS = ("Violent", "Hatred", "Disrespect", "Untrusting", "Dislike", "Guarded",
             "Neutral", "Like", "Respect", "Loyal", "Trust", "Charmed", "Reverence")

def change_demeanor(state, key, delta):
    """Bound ordinary persistent changes in rolling fictional-time windows.

    Month is interpreted as 30 days. Temporary changes and exceptional
    rulings are deliberately not supported by this first implementation.
    """
    now = datetime.fromisoformat(state["time"])
    history = [e for e in state["relationship_changes"] if e["npc"] == key and e["delta"] != 0]
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

def consequential_demeanor(state, rules, request):
    """Apply the existing persistent Demeanor limits to a witnessed incident."""
    if not rules.get("consequential_demeanor") or not isinstance(request, dict) or set(request) != {"npc", "observation", "severity", "basis"}:
        raise ValueError("invalid consequential Demeanor request")
    npc, oid, severity = request["npc"], request["observation"], request["severity"]
    if not isinstance(npc, str) or npc not in state["npcs"] or state["ending"] or state["dxd"].get("activity", {}).get("status") == "asleep":
        raise ValueError("Demeanor participant unavailable")
    if state["npcs"][npc]["location"] != state["location"] or not npc_available(state, rules, {"npc": npc, "location": state["location"]}):
        raise ValueError("Demeanor requires available local NPC")
    obs = next((o for o in state["action_observations"] if o["id"] == oid and o["npc"] == npc), None)
    if not obs or obs["kind"] != "witnessed" or obs["actor"] != "pc" or obs["turn"] != state["turn"] or obs["location"] != state["location"]:
        raise ValueError("Demeanor requires current directly attributed conduct")
    if not isinstance(severity, str) or severity not in rules["consequential_demeanor"]:
        raise ValueError("invalid Demeanor severity")
    if any(e["npc"] == npc and e.get("action") == obs["action"] for e in state["relationship_changes"]):
        raise ValueError("incident already adjudicated for Demeanor")
    basis = establishment.text(request["basis"], 240)
    old = state["relationships"][npc]
    count = len(state["relationship_changes"])
    change_demeanor(state, npc, rules["consequential_demeanor"][severity])
    provenance = {"source": "consequential_conduct", "action": obs["action"], "observation": oid,
                  "severity": severity, "basis": basis, "turn": state["turn"],
                  "requested_delta": rules["consequential_demeanor"][severity]}
    if len(state["relationship_changes"]) == count:
        # Record adjudication even when ordinary limits prevent a change.
        state["relationship_changes"].append({"npc": npc, "at": state["time"], "delta": 0, **provenance})
    else:
        state["relationship_changes"][-1].update(provenance)
    assert state["relationships"][npc] <= old

def social_demeanor(state, rules, request):
    """Bounded consequence of an actual exchange, not a trust meter or forced forgiveness."""
    if not rules.get("demeanor") or not (rules.get("social_epistemic") or rules.get("social_demeanor")) or not isinstance(request, dict) or set(request) != {"npc", "claims", "kind", "basis"}:
        raise ValueError("invalid social Demeanor request")
    nid, refs, kind = request["npc"], request["claims"], request["kind"]
    if not isinstance(nid, str) or nid not in state["npcs"] or state["ending"] or state["dxd"].get("activity", {}).get("status") == "asleep":
        raise ValueError("social Demeanor unavailable")
    if not epistemic.conversation_available(state, rules, nid, npc_available):
        raise ValueError("social Demeanor requires available local NPC")
    if kind not in ("harm", "reparation"):
        raise ValueError("unsupported social consequence")
    if not isinstance(refs, list) or not 1 <= len(refs) <= 4 or any(type(i) is not int for i in refs) or len(set(refs)) != len(refs):
        raise ValueError("invalid social consequence claims")
    claims = [c for c in state["dialogue"] if c["id"] in refs and {c["speaker"], c["listener"]} == {"pc", nid}
              and c["turn"] == state["turn"] and c["location"] == state["location"]]
    if len(claims) != len(refs) or not any(c["speaker"] == "pc" for c in claims):
        raise ValueError("consequence requires current actual player conduct")
    history = state["relationship_changes"]
    if any(e["npc"] == nid and (set(e.get("claims", [])) & set(refs) or
           e.get("source") == "social_conduct" and e.get("turn") == state["turn"]) for e in history):
        raise ValueError("social consequence already adjudicated")
    if kind == "reparation":
        if not any(c["speaker"] == nid for c in claims) or not any(e["npc"] == nid and e["delta"] < 0 for e in history):
            raise ValueError("reparation requires acknowledged conduct and prior relationship harm")
    basis = establishment.text(request["basis"], 240)
    count = len(history)
    delta = 1 if kind == "reparation" else -1
    change_demeanor(state, nid, delta)
    provenance = {"source": "social_conduct", "kind": kind, "claims": list(refs),
                  "basis": basis, "turn": state["turn"], "requested_delta": delta}
    if len(history) == count:
        history.append({"npc": nid, "at": state["time"], "delta": 0, **provenance})
    else:
        history[-1].update(provenance)

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

def activity_segment(state, rules, seconds, mode, *, safe=False, interruptible=False, engaged=None):
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
        medical.interrupt_unavailable(state, rules, npc_available, engaged=engaged, moving=mode == "travel")
        npc_agenda.observe_boundary(state, rules, engaged=engaged)
        boundary = next(b for b in boundaries if b > cursor)
        boundary = timed_details.next_boundary(state, cursor, boundary)
        boundary = npc_time.next_boundary(state, cursor, boundary)
        boundary = npc_travel.next_boundary(state, cursor, boundary)
        if "narrative_events" in state:
            interval = narrative_events.next_boundary(state, rules)
            if interval is not None:
                boundary = min(boundary, cursor + timedelta(seconds=interval))
        injury = pc.get("injury")
        interval = dxd_injury.next_boundary(injury)
        if interval is not None:
            boundary = min(boundary, cursor + timedelta(seconds=interval))
        stun = dxd_hitpoints.stun_boundary(pc)
        if stun is not None:
            boundary = min(boundary, cursor + timedelta(seconds=stun))
        awakening = dxd_hitpoints.awakening_boundary(pc)
        if awakening is not None:
            boundary = min(boundary, cursor + timedelta(seconds=awakening))
        span = int((boundary - cursor).total_seconds())
        before = dxd_conditions.degrees(pc["concerns"])["stress"]
        actual = span if mode == "incapacitated" else dxd_conditions.advance_activity(pc["concerns"], clock, span, mode, safe=safe,
                                                 seed=state["seed"], attributes=pc["attributes"])
        awakened = False
        if "hitpoints" in pc:
            dxd_hitpoints.advance(pc, actual, restful=mode in ("rest", "quiet", "sleep", "low_energy"))
            awakened = dxd_hitpoints.advance_unconscious(pc, actual)
        if injury:
            dxd_injury.advance(injury, actual)
            regime = rules.get("injury_recuperation", {}).get("regime")
            if regime:
                eligible = (safe and mode in ("rest", "quiet", "sleep") and engaged is None
                            and injury["capacity"] > injury["injury"] > 0
                            and state["location"] in rules["injury_recuperation"]["locations"])
                recovered = dxd_injury.recuperate(injury, actual,
                    regime="post_dying" if injury.get("ever_dying") else regime, eligible=eligible)
                if recovered:
                    state["observations"].append(f"Extended recuperation restored {recovered} Bodypoints.")
        dxd_morale.calm(pc["morale"], safe=safe, stress_degrees_removed=before - dxd_conditions.degrees(pc["concerns"])["stress"])
        cursor += timedelta(seconds=actual)
        state["time"] = cursor.isoformat()
        npc_time.advance(state, rules, actual, engaged=engaged)
        narrative_events.advance_time(state, rules, actual)
        advance_events(state, rules, cursor)
        npc_travel.resolve(state, rules, cursor)
        medical.interrupt_unavailable(state, rules, npc_available, engaged=engaged, moving=mode == "travel")
        timed_details.resolve(state, rules, cursor, npc_available, establishment.local_entities)
        npc_agenda.observe_boundary(state, rules, engaged=engaged)
        if injury and dxd_injury.projection(injury)["status"] == "dead":
            reason = "character_death"
            break
        if dxd_hitpoints.advance_stun(pc, actual):
            state["observations"].append("You lose consciousness.")
            reason = "unconsciousness"
            break
        if awakened:
            state["observations"].append("You regain consciousness.")
            reason = "regained_consciousness"
            break
        if mode not in ("sleep", "incapacitated") and clock["pending_sleep_seconds"] == 0:
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
    if "task_duration" in a:
        state["last_result"]["task_duration"] = copy.deepcopy(a["task_duration"])
    if reason:
        state["last_result"]["interrupted"] = reason
    if state.get("transitions") and state["transitions"][-1]["turn"] == state["turn"]:
        state["last_result"]["transition"] = state["transitions"][-1]
    if "activity" in state["dxd"]:
        pc = state["dxd"]
        dxd_conditions.refresh_sleep_limit(pc["concerns"], pc["activity"], pc["attributes"])
    pacing.reconcile_scene(state, rules)
    pacing.record(state, a)
    state["history"].append(history_entry(action, proposal, a.get("commitment")))
    if ("pacing" not in rules and state["turn"] >= rules["max_turns"]) or not options(state, rules):
        state["ending"] = ending_projection(state, rules, "limit", action)
    return state

def step(state, action, proposal=None, commitment=None):
    _, rules = load(state["scenario"])
    return _step(copy.deepcopy(state), rules, action, proposal, commitment)


def _step(state, rules, action, proposal=None, commitment=None):
    if state["ending"]:
        raise ValueError("session ended; further gameplay unavailable")
    if dxd_hitpoints.incapacitated(state["dxd"]) and (action != "await_assistance" or proposal is not None or commitment is not None):
        raise ValueError("physical incapacity prevents voluntary action")
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
    a = proposals.resolve_duration(state, a)
    started = datetime.fromisoformat(state["time"])
    elapsed = started + timedelta(seconds=a["duration_seconds"])
    if elapsed > datetime.fromisoformat(rules["end"]):
        raise ValueError("action exceeds scenario deadline")
    state["turn"] += 1
    if rules.get("routine_observations"):
        state["routine_source"] = None
    clock = state["dxd"].get("activity")
    if action == "await_assistance":
        reason = activity_segment(state, rules, a["duration_seconds"], "incapacitated")
        return finish_activity(state, rules, action, a, reason != "character_death", reason)
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
    npc_agenda.observe_boundary(state, rules, engaged=a.get("npc"))
    if rules.get("routine_observations"):
        activity_observers = _available_local_npcs(state, rules)
    if clock:
        # Events during travel may invalidate the intended local action.
        if not _local_action_available(state, rules, a):
            return finish_activity(state, rules, action, a, False, "availability_changed", proposal)
        engaged = a.get("npc")
        sleep_episode = state["npcs"][engaged].get("activity", {}).get("sleep_episode") if engaged else None
        if engaged:
            npc_time.interrupt(state, engaged)
        mode = a.get("activity", "active")
        if action == "sleep_room":
            for key, amount in a.get("cost", {}).items():
                state["resources"][key] -= amount
            dxd_conditions.begin_sleep(state["dxd"]["concerns"], clock, state["dxd"]["attributes"])
        elif a.get("cost"):
            for key, amount in a["cost"].items():
                state["resources"][key] -= amount
        reason = activity_segment(state, rules, a.get("local_seconds", a["duration_seconds"]), mode,
                                  safe=a.get("safe", False), interruptible=mode in ("rest", "low_energy", "sleep", "restorative", "quiet"), engaged=engaged)
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
        if rules.get("npc_lifecycle") and engaged and state["npcs"][engaged].get("activity", {}).get("sleep_episode") != sleep_episode:
            return finish_activity(state, rules, action, a, False, "npc_sleep_interruption", proposal)
        if not _local_action_available(state, rules, a):
            return finish_activity(state, rules, action, a, False, "availability_changed", proposal)
    else:
        # Dated milestones precede completion effects, including at a tie.
        advance_events(state, rules, elapsed)
        state["time"] = elapsed.isoformat()
        npc_time.advance_abstract(state, rules, started, elapsed, engaged=a.get("npc"))
        if not _local_action_available(state, rules, a):
            for key, amount in a.get("cost", {}).items():
                state["resources"][key] -= amount
            return finish_activity(state, rules, action, a, False, "availability_changed", proposal)
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
    if a.get("danger_beat"):
        beats.record(state, rules, a, primary_result)
    if a.get("local_capability"):
        proposals.record_local(state, a, success, primary_result)
    narrative_events.complete_action(state, rules, a, success, a.get("local_seconds", a["duration_seconds"]))
    if clock:
        dxd_conditions.refresh_sleep_limit(state["dxd"]["concerns"], clock, state["dxd"]["attributes"])
    state["last_result"] = {"action": action, "success": success}
    if "task_duration" in a:
        state["last_result"]["task_duration"] = copy.deepcopy(a["task_duration"])
    if rules.get("routine_observations"):
        available = _available_local_npcs(state, rules)
        state["routine_source"] = {"turn": state["turn"], "location": state["location"],
                                   "eligible_observers": sorted(available),
                                   "activity_observers": sorted(available & activity_observers)}
    if a.get("preparation_saved_seconds"):
        state["last_result"]["preparation_saved_seconds"] = a["preparation_saved_seconds"]
    if proposal is not None:
        if primary_result is not None:
            state["last_result"]["adjudication"] = {k: primary_result[k] for k in ("passed", "dos", "dof", "margin")}
        else:
            state["last_result"]["adjudication"] = {"passed": success, "resolution": "certain"}
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
        state["ending"] = ending_projection(state, rules, action if terminal else "limit", action)
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

def ending_projection(state, rules, reason, action):
    """Common terminal record for completed and interrupted activities."""
    if state["dxd"].get("injury") and dxd_injury.projection(state["dxd"]["injury"])["status"] == "dead":
        reason = "character_death"
    flags = rules.get("ending_flags", {
        "account_prepared": "written_account", "account_relayed": "account_relayed",
        "account_entrusted": "account_entrusted"})
    return {"reason": reason, "evidence_count": len(state["discoveries"]),
            **{key: flag in state["flags"] for key, flag in flags.items()},
            "epilogue": ("Your character has died. The investigation ends here." if reason == "character_death" and reason not in rules["ending_text"] else rules["ending_text"][reason]), "scores": scores(state, action)}


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
    if state["dxd"].get("injury") and dxd_injury.projection(state["dxd"]["injury"])["status"] == "dead":
        self_preserved = 0
    contained = min(100, 10 + 18 * state["containment"])
    return {"Truth Preserved": truth / 10, "Self Preserved": self_preserved / 10,
            "Horror Contained": contained / 10}

def apply_memory(state, event, memory):
    """Enrich a committed Inspiration's wording, never its mechanics.

    Only the latest Turn's already-triggered Inspiration is eligible.
    Wording is untrusted narrative input, not a source of new facts.
    """
    if state["ending"]:
        raise ValueError("session ended; memory editing unavailable")
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

def _apply_narrative(state, rules, request):
    pacing.control(state, rules, request)
    state["history"].append({"narrative": copy.deepcopy(request)})


def narrative_step(state, request):
    result = copy.deepcopy(state)
    _, rules = load(result["scenario"])
    _apply_narrative(result, rules, request)
    return result

def narrative(path, request, revision):
    return _commit(path, revision, narrative_step, request)

def _apply_dialogue(state, rules, request):
    if state["ending"]:
        raise ValueError("session ended; further dialogue unavailable")
    if dxd_injury.incapacitated(state["dxd"].get("injury")):
        raise ValueError("physical incapacity prevents dialogue")
    epistemic.record(state, rules, request, npc_available)
    npc_time.interrupt(state, request["npc"])
    state["history"].append({"dialogue": copy.deepcopy(request)})


def dialogue_step(state, request):
    result = copy.deepcopy(state)
    _, rules = load(result["scenario"])
    _apply_dialogue(result, rules, request)
    return result

def dialogue(path, request, revision):
    return _commit(path, revision, dialogue_step, request)

def _apply_establishment(state, rules, request):
    if state["ending"]:
        raise ValueError("session ended; further establishment unavailable")
    if isinstance(request, dict) and set(request) == {"assisted_awakening"}:
        medical.awaken(state, rules, request["assisted_awakening"], npc_available, establishment.text)
        state["history"].append({"establish": copy.deepcopy(request)})
        return
    if isinstance(request, dict) and set(request) == {"medical_bandage"}:
        medical.schedule(state, rules, request["medical_bandage"], npc_available, establishment.text)
        state["history"].append({"establish": copy.deepcopy(request)})
        return
    if dxd_injury.incapacitated(state["dxd"].get("injury")):
        raise ValueError("physical incapacity prevents ordinary establishment")
    if isinstance(request, dict) and set(request) == {"consequential_demeanor"}:
        consequential_demeanor(state, rules, request["consequential_demeanor"])
    elif isinstance(request, dict) and set(request) == {"social_demeanor"}:
        social_demeanor(state, rules, request["social_demeanor"])
    else:
        establishment.record(state, rules, request, npc_available)
    npc_agenda.observe_boundary(state, rules)
    state["history"].append({"establish": copy.deepcopy(request)})


def establish_step(state, request):
    result = copy.deepcopy(state)
    _, rules = load(result["scenario"])
    _apply_establishment(result, rules, request)
    return result

def batch_step(state, request):
    """Apply ordered, nonmechanical operations to an isolated checkpoint.

    Constituent history entries retain existing replay and sequence semantics.
    No partial checkpoint is returned or saved on failure.
    """
    _, rules = load(state["scenario"])
    if not rules.get("narrative_batch") or state["ending"] or state["dxd"].get("activity", {}).get("status") == "asleep":
        raise ValueError("narrative batch unavailable")
    if not isinstance(request, dict) or set(request) != {"operations"}:
        raise ValueError("invalid narrative batch")
    operations = request["operations"]
    if not isinstance(operations, list) or not 1 <= len(operations) <= 24:
        raise ValueError("narrative batch requires 1 to 24 operations")
    # Existing validators and history writers remain authoritative. One
    # private working copy suffices for the whole atomic batch.
    result = copy.deepcopy(state)
    for index, op in enumerate(operations, 1):
        if not isinstance(op, dict) or len(op) != 1:
            raise ValueError(f"invalid narrative operation {index}")
        try:
            if "dialogue" in op:
                _apply_dialogue(result, rules, op["dialogue"])
            elif "establish" in op:
                _apply_establishment(result, rules, op["establish"])
            else:
                raise ValueError("unsupported narrative operation")
        except ValueError as exc:
            raise ValueError(f"narrative operation {index}: {exc}") from exc
    return result

def establish(path, request, revision):
    transition = batch_step if isinstance(request, dict) and "operations" in request else establish_step
    return _commit(path, revision, transition, request)

def verify(state):
    """Replay against a single source snapshot, never the caller's state.

    Preserve the historic ordering of Inspiration edits and all constituent
    operations. Each transition receives its own rules copy because legacy
    helpers may attach references from authored action records to state.
    """
    sid = state["scenario"]
    story, rules = load(sid)
    if state.get("source") != digest([story, rules]):
        raise ValueError("session source revision mismatch; use matching scenario sources or start a fresh session")
    level = state.get("opportunity_latitude")
    if "opportunity_latitude" in state:
        latitude.validate(level)
    replay = _initial(sid, state["seed"], copy.deepcopy(story), copy.deepcopy(rules),
                      opportunity_latitude=level)
    edits = state["dxd"]["memory_edits"]
    cursor = 0
    for entry in state["history"]:
        operation = copy.deepcopy(entry)
        config = copy.deepcopy(rules)
        if isinstance(operation, dict) and "establish" in operation:
            _apply_establishment(replay, config, operation["establish"])
            continue
        if isinstance(operation, dict) and "dialogue" in operation:
            _apply_dialogue(replay, config, operation["dialogue"])
            continue
        if isinstance(operation, dict) and "narrative" in operation:
            _apply_narrative(replay, config, operation["narrative"])
            continue
        if isinstance(operation, dict) and "commitment" in operation:
            replay = _step(replay, config, operation["action"], operation.get("proposal"), operation["commitment"])
        elif isinstance(operation, dict):
            proposal = operation["proposal"]
            replay = _step(replay, config, proposal["action"], proposal)
        else:
            replay = _step(replay, config, operation)
        while cursor < len(edits) and edits[cursor]["turn"] == replay["turn"]:
            e = edits[cursor]
            apply_memory(replay, e["event"], e["memory"])
            cursor += 1
    if cursor != len(edits) or replay != state:
        raise ValueError("session replay mismatch")


def view(state, *, full_history=False):
    _, rules = load(state["scenario"])
    return projections.player_view(state, rules, options(state, rules),
                                   npc_available, digest, DEMEANORS,
                                   full_history=full_history)


def gm_context(state, *, compact=False):
    story, rules = load(state["scenario"])
    return projections.referee_view(state, story, rules, options(state, rules),
                                     npc_available, digest, DEMEANORS,
                                     compact=compact)


def inspect_gm(path, *, compact=False):
    return gm_context(_verified_read(path), compact=compact)

def start(sid, path, seed, opportunity_latitude=None):
    if path.exists():
        raise ValueError("session already exists")
    state = initial(sid, seed, opportunity_latitude)
    public = view(state)
    save(path, state)
    return public

def inspect(path, *, full_history=False):
    return view(_verified_read(path), full_history=full_history)

def act(path, action, revision, proposal=None, commitment=None):
    return _commit(path, revision, step, action, proposal, commitment)

def enrich_memory(path, event, memory, revision):
    def edit(state, event, memory):
        apply_memory(state, event, memory)
        return state
    return _commit(path, revision, edit, event, memory)


def _verified_read(path):
    state = read(path)
    verify(state)
    return state


def _commit(path, revision, transition, *args):
    """One mutation boundary for every narrative session operation.

    Verify before accepting input; verify and project the new state before
    atomically replacing the checkpoint. A failed transition or projection
    never writes a partial result. Concurrent writers remain unsupported.
    """
    state = _verified_read(path)
    if digest(state) != revision:
        raise ValueError("stale session revision")
    result = transition(state, *args)
    verify(result)
    public = view(result)
    save(path, result)
    return public

