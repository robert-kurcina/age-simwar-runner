"""Read-only, player-scoped resumption packet from the existing public view.

This module must not inspect raw NPC state or GM projections. All statements
are already actor-visible; the packet only orders and bounds them.
"""
import copy


def recap(public):
    """Produce a deterministic resumption snapshot without modifying a session."""
    # Callers must pass mythos.view(state), never the authoritative state.
    if "revision" not in public or "choices" not in public:
        raise ValueError("recap requires a verified player view")
    scene = public.get("scene", {})
    pacing = public.get("pacing", {})
    return {
        "audience": "player",
        "revision": public["revision"],
        "scenario": public["scenario"],
        "time": public["time"],
        "location": public["location"],
        "turn": public["turn"],
        "ending": copy.deepcopy(public.get("ending")),
        "current_situation": {
            "description": scene.get("description"),
            "pressure": copy.deepcopy(scene.get("pressure", [])),
            "active_spotlight": copy.deepcopy(pacing.get("current_spotlight")),
            "last_result": copy.deepcopy(public.get("last_result")),
        },
        "earned_information": {
            "discoveries": copy.deepcopy(public.get("discoveries", [])),
            "recent_observations": copy.deepcopy(public.get("observations", [])[-8:]),
            "recent_exchanges": copy.deepcopy(public.get("dialogue", [])[-8:]),
            "local_records": copy.deepcopy(public.get("local_records", [])[-8:]),
        },
        "social_continuity": {
            "contacts": copy.deepcopy(public.get("contacts", [])),
            "agreements": copy.deepcopy(public.get("narrative_agreements", [])),
        },
        "practical_context": {
            "inventory": copy.deepcopy(public.get("inventory", [])),
            "resources": copy.deepcopy(public.get("resources", {})),
            "condition": copy.deepcopy(public.get("condition", {})),
            "event_pressure": copy.deepcopy(public.get("event_pressure", {})),
        },
        "available_next_actions": copy.deepcopy(public.get("choices", [])),
    }
