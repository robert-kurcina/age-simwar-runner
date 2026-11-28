"""Read-only shared-memory cues, not new facts or a second memory ledger."""
from datetime import datetime
from age_runtime.mythos import agreements, epistemic

def age(state, entry):
    return {"turns_ago": state["turn"] - entry["turn"],
            "minutes_ago": int((datetime.fromisoformat(state["time"]) -
                                datetime.fromisoformat(entry["at"])).total_seconds() // 60)}

def projection(state, participants):
    """Bounded candidates from material exchanges known to both participants."""
    public = epistemic.public_projection(state)
    current_agreements = agreements.project(state)
    result = {}
    for npc in sorted(participants):
        shared = [e for e in public if {e["speaker"], e["listener"]} == {"pc", npc}]
        witnessed = [o for o in state.get("action_observations", [])
                     if o["npc"] == npc and o["kind"] == "witnessed" and o["actor"] == "pc"]
        routines = [o for o in state.get("routine_observations", []) if o["npc"] == npc]
        if not shared and not witnessed and not routines:
            continue
        by_id = {e["id"]: e for e in shared}
        # Recent exchanges plus older significant material, never private
        # emotional interpretation, secret facts or unearned discoveries.
        important = {e["id"] for e in state.get("dialogue", [])
                     if e["id"] in by_id and e.get("npc_reaction", {}).get("significance")}
        important.update(i for e in state.get("emotional_episodes", [])
                         if e["npc"] == npc for i in e["claim_ids"] if i in by_id)
        recent = shared[-4:]
        older = [e for e in shared[:-4] if e["id"] in important][-3:]
        cues = [{"kind": "prior_utterance", "claim_id": e["id"],
                 "speaker": e["speaker"], "claim": e["claim"], "at": e["at"],
                 "location": e["location"], **age(state, e)} for e in older + recent]
        active = [a for a in current_agreements.values()
                  if a["npc"] == npc and a["status"] == "active"]
        # Prefer commitments over incidental permissions, then recency.
        active.sort(key=lambda a: (a["kind"] == "commitment", a["at"], a["id"]), reverse=True)
        obligations = [{"id": a["id"], "kind": a["kind"], "issuer": a["issuer"],
                        "terms": a["terms"], "condition": a["condition"],
                        "claim_ids": list(a["claim_ids"]), **age(state, a)}
                       for a in active[:4]]
        significant = {e.get("observation") for e in state.get("emotional_episodes", []) if e["npc"] == npc}
        selected = witnessed[-4:]
        older_actions = [o for o in witnessed[:-4] if o["id"] in significant][-3:]
        actions = [{k: o[k] for k in ("id", "object", "outcome", "condition", "at", "location")}
                   | ({"function": o["function"]} if "function" in o else {}) | age(state, o)
                   for o in older_actions + selected]
        # Routine observations are NPC-owned and concern the PC's actual
        # conduct. Recall the facts, never the private interpretation.
        salient_refs = {ref for p in state.get("behavioral_recognition", [])
                        if p["npc"] == npc for ref in p["evidence"]}
        older_routines = [o for o in routines[:-4] if o["id"] in salient_refs][-3:]
        routine_cues = [{k: o[k] for k in ("id", "kind", "text", "at", "location")}
                        | age(state, o) for o in older_routines + routines[-4:]]
        result[npc] = {"last_shared_exchange": age(state, shared[-1]) if shared else None,
                       "observed_routines": routine_cues,
                       "shared_actions": actions,
                       "utterances": cues, "active_agreements": obligations}
    return result
