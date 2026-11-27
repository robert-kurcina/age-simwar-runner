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
        "opportunity_latitude": public.get("opportunity_latitude", "balanced"),
        "time": public["time"],
        "location": public["location"],
        "turn": public["turn"],
        "ending": copy.deepcopy(public.get("ending")),
        "current_situation": {
            "description": scene.get("description") or public.get("opening"),
            "pressure": copy.deepcopy(scene.get("pressure", [])),
            "active_spotlight": copy.deepcopy(pacing.get("current_spotlight")),
            "last_result": copy.deepcopy(public.get("last_result")),
        },
        "earned_information": {
            "discoveries": copy.deepcopy(public.get("discoveries", [])),
            "recent_observations": copy.deepcopy(public.get("observations", [])[-8:]),
            "recent_exchanges": copy.deepcopy(public.get("dialogue", [])[-8:]),
            "local_records": copy.deepcopy(public.get("local_records", [])[-8:]),
            "established_details": copy.deepcopy(public.get("established_details", [])),
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
            "activity": copy.deepcopy(public.get("activity")),
            "memory_prompt": copy.deepcopy(public.get("memory_prompt")),
        },
        "available_next_actions": copy.deepcopy(public.get("choices", [])),
    }


def recall(public, query, *, limit=12, offset=0):
    """Search only earned, player-visible records, keeping original provenance.

    Query is literal, case-insensitive text; matching is not semantic inference.
    Stable source ordering and pagination keep long histories usable.
    """
    import json
    if "revision" not in public or "choices" not in public:
        raise ValueError("recall requires a verified player view")
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 160:
        raise ValueError("recall query must contain 1 to 160 characters")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("recall limit must be 1 to 50")
    if type(offset) is not int or offset < 0:
        raise ValueError("recall offset must be a nonnegative integer")
    needle = query.strip().casefold()
    results = []
    # Include old claims even after they leave the recap's recent window.
    for field, kind in (
        ("discoveries", "discovery"),
        ("observations", "observation"),
        ("dialogue", "communicated_claim"),
        ("local_records", "local_record"),
        ("narrative_agreements", "agreement"),
        ("contacts", "contact"),
        ("memories", "memory"),
        ("remembered_details", "historical_detail"),
        ("established_details", "current_local_detail"),
    ):
        for index, record in enumerate(public.get(field, [])):
            if needle in json.dumps(record, ensure_ascii=False, sort_keys=True).casefold():
                results.append({"kind": kind, "source": field, "index": index,
                                "record": copy.deepcopy(record)})
    end = offset + limit
    return {"audience": "player", "revision": public["revision"],
            "query": query.strip(), "total": len(results), "offset": offset,
            "next_offset": end if end < len(results) else None,
            "matches": results[offset:end]}
