"""Reviewed successor transition; no resurrection or implicit inheritance."""
import copy
from age_runtime.core import (
    dxd_character, dxd_conditions, dxd_context, dxd_hitpoints,
    dxd_injury, dxd_morale, dxd_progression,
)
from age_runtime.mythos import pacing, medical, npc_agenda


def apply(state, rules, request):
    if not isinstance(request, dict) or set(request) != {"profile"}:
        raise ValueError("invalid replacement request")
    profiles = rules.get("replacement_profiles", {})
    key = request["profile"]
    if not isinstance(key, str) or key not in profiles:
        raise ValueError("replacement profile not reviewed")
    if (not state.get("protagonist") or not state.get("ending")
            or state["ending"]["reason"] != "character_death"
            or dxd_injury.projection(state["dxd"]["injury"])["status"] != "dead"):
        raise ValueError("replacement requires irreversible character death")
    if state["time"] >= rules["end"]:
        raise ValueError("scenario horizon exhausted")
    # Until remaining cross-character ledgers are migrated, fail closed.
    if any(state.get(k) for k in ("established_details", "local_records",
                                  "incidental_people", "emotional_episodes",
                                  "behavioral_recognition", "routine_observations",
                                  "npc_expectations", "progression")):
        raise ValueError("replacement requires reviewed continuity for existing personal records")
    if any(e["status"] == "scheduled" for e in state.get("timed_detail_events", [])):
        raise ValueError("replacement requires resolution of pending timed commitments")
    cfg = profiles[key]
    archive = state.setdefault("retired_protagonists", [])
    if any(e["profile_key"] == key for e in archive) or state["protagonist"].get("profile_key") == key:
        raise ValueError("replacement profile already used")
    required = {"role", "location", "inventory", "attributes", "body", "character_profile",
                "resources", "relationships", "favor", "awake_seconds", "entry_basis"}
    if set(cfg) != required or cfg["location"] not in rules["locations"]:
        raise ValueError("invalid reviewed replacement profile")
    if not isinstance(cfg["entry_basis"], str) or not cfg["entry_basis"].strip():
        raise ValueError("replacement requires reviewed entry circumstances")
    if set(cfg["resources"]) != set(state["resources"]) or any(type(v) is not int or v < 0 for v in cfg["resources"].values()):
        raise ValueError("invalid replacement resources")
    if set(cfg["relationships"]) != set(state["relationships"]) or any(type(v) is not int or not -6 <= v <= 6 for v in cfg["relationships"].values()):
        raise ValueError("invalid replacement relationships")
    if type(cfg["favor"]) is not int or cfg["favor"] < 0 or type(cfg["awake_seconds"]) is not int or cfg["awake_seconds"] < 0:
        raise ValueError("invalid replacement Favor or awake time")
    body = dxd_character.derive(cfg["attributes"], cfg["body"])
    profile = copy.deepcopy(cfg["character_profile"])
    prof = profile["proficiencies"]
    if rules["dxd"].get("professional_progression"):
        progress = rules["dxd"]["professional_progression"]
        prof["qualification"] = dxd_progression.describe(profile, progress["careers"])
        if "skill_im" in progress:
            prof["progression"]["fast_track_audit"] = dxd_progression.audit_skills(profile, progress["skill_im"])
    old = state["dxd"]
    pc = {"attributes": body["attributes"], "body": body,
          "skills": copy.deepcopy(prof["skills"]), "traits": copy.deepcopy(prof["traits"]),
          "favor": cfg["favor"], "tests": [], "inspirations": [], "memory_edits": [],
          "morale": dxd_morale.initial(), "concerns": dxd_conditions.initial(body["attributes"]),
          "inactive_major_attributes": copy.deepcopy(old["inactive_major_attributes"]),
          "inactive_major_bodies": copy.deepcopy(old["inactive_major_bodies"])}
    pc["concerns"]["capacity"]["resilience"] += pc["skills"].get("Grit", 0)
    pc["injury"] = dxd_injury.initial(body["physical"]["bodypoints"], body["attributes"]["SIZ"],
                                      pc["concerns"]["capacity"]["recovery_rate"])
    if rules.get("native_hitpoints"):
        pc["hitpoints"] = dxd_hitpoints.initial(body["physical"]["base_hitpoints"])
    if rules.get("emotional_commitment"):
        pc["commitments"] = []
    if "activity" in rules:
        pc["activity"] = dxd_conditions.activity_initial(body["attributes"], cfg["awake_seconds"])
    archive.append(copy.deepcopy({
        "identity": state["protagonist"], "profile_key": state["protagonist"].get("profile_key"),
        "ending": state["ending"], "location": state["location"], "dxd": old,
        "character_profile": state["character_profiles"]["pc"], "inventory": state["inventory"],
        "resources": state["resources"], "relationships": state["relationships"],
        "discoveries": state["discoveries"], "observations": state["observations"],
    }))
    if state.get("pacing", {}).get("current"):
        pacing.control(state, rules, {"kind": "abandon", "id": state["pacing"]["current"]})
    state["protagonist"] = {"id": f"pc:{len(archive) + 1}", "profile_key": key,
                            "role": cfg["role"], "entered_at": state["time"],
                            "entered_turn": state["turn"], "entry_basis": cfg["entry_basis"]}
    state["dxd"] = pc
    state["character_profiles"]["pc"] = profile
    state["attributes"] = copy.deepcopy(cfg["attributes"])
    for k in ("inventory", "resources", "relationships", "location"):
        state[k] = copy.deepcopy(cfg[k])
    state["discoveries"] = []
    state["observations"] = []
    state["last_result"] = None
    state["ending"] = None
    if "routine_source" in state:
        state["routine_source"] = None
    if rules.get("native_disabilities"):
        dxd_context.initialize(state)
    pacing.reconcile_scene(state, rules)
    npc_agenda.observe_boundary(state, rules)
    state["history"].append({"replace_protagonist": copy.deepcopy(request)})
