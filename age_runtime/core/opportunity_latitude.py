"""Shared facilitator policy; never changes adjudication or world state."""

LEVELS = ("permissive", "balanced", "strict")
DEFAULT = "balanced"
FAILURE_CATEGORIES = {
    "method_failure": "Original approach is no longer viable; alternatives may exist.",
    "opportunity_closure": "A particular resource, agreement or timed option is unavailable.",
    "objective_failure": "Original objective is unreachable; mitigation or other objectives may remain.",
    "terminal_failure": "No further meaningful progress is possible within the established scenario."
}
GUIDANCE = {
    "permissive": "Actively explore novel credible recovery routes, including player-authored alternatives, before concluding failure.",
    "balanced": "Explore plausible alternatives proportionate to the stakes; preserve irreversible consequences and accept reduced objectives.",
    "strict": "Explain closed modeled opportunities and remaining supported options; do not seek extraordinary exceptions merely to avert failure."
}


def validate(level):
    if not isinstance(level, str) or level not in LEVELS:
        raise ValueError("invalid opportunity latitude")
    return level


def select(default=DEFAULT, override=None):
    validate(default)
    return default if override is None else validate(override)


def policy(level=DEFAULT):
    return {
        "level": validate(level),
        "guidance": GUIDANCE[level],
        "failure_categories": dict(FAILURE_CATEGORIES),
        "constraints": [
            "Respect physics, time, logistics, resources, established facts and prior consequences.",
            "Respect factional needs, psychology, authority and independent consent.",
            "Distinguish the current modeled approach from all conceivable approaches.",
            "Treat unsupported novel solutions as proposals, not accomplished facts.",
            "Use existing validated adjudication and explicit confirmation; never invent effects, resources or time.",
            "Do not declare terminal failure from a single closed opportunity or project bound.",
            "Do not continue an ended session or reopen an irreversible outcome through this policy."
        ]
    }


def assess_projects(projects, level=DEFAULT, complete=False):
    """Actor-local flags; never infer global failure from one project."""
    validate(level)
    return [
        {"project": p["id"], "category": "opportunity_closure",
         "scope": "current-modeled-approach",
         "reason": "Remaining stages exceed the maximum number of project resolutions.",
         "recovery_guidance": ("Session ended; assess achieved outcomes only." if complete else GUIDANCE[level]),
         "terminal_failure_established": False}
        for p in projects
        if not p.get("complete") and
        p.get("horizon", {}).get("possible_at_maximum_rate") is False
    ]


def recovery_assessment(brief, level=DEFAULT, complete=False):
    """Read-only recovery inventory, not a feasibility search or adjudicator."""
    from copy import deepcopy
    validate(level)
    projects = brief.get("projects", [])
    closures = assess_projects(projects, level, complete)
    closed = {c["project"] for c in closures}
    alternatives = []
    if not complete:
        for option in brief.get("options", []):
            assessment = option.get("assessment", {})
            if option["kind"] == "capacity":
                if assessment.get("reason") in ("project_complete", "capacity_at_limit"):
                    continue
                if assessment.get("project_effect") == "already_clear":
                    continue
                alternatives.append({
                    "kind": "modeled_action", "id": option["id"],
                    "project": assessment["project"],
                    "scope": ("mitigation_only" if assessment["project"] in closed
                              else "potential_progress"),
                    "status": ("available_now" if assessment["currently_feasible"]
                               else "conditional"),
                    "resource": assessment["resource"], "cost": assessment["cost"],
                    "reported_balance": assessment["reported_balance"],
                    "constraint": assessment.get("reason"),
                    "effect_if_fulfilled": assessment.get("if_fulfilled"),
                    "project_effect": assessment.get("project_effect"),
                })
            elif option["kind"] in ("consent", "request", "transfer"):
                alternatives.append({
                    "kind": "modeled_action", "id": option["id"],
                    "status": ("conditional" if option["kind"] == "consent"
                               or assessment.get("currently_feasible") is False
                               else "available_for_submission"),
                    "action_kind": option["kind"],
                    "assessment": assessment,
                    "agreement": option.get("agreement"),
                    "scope": "other_objectives_or_mitigation_unverified",
                })
        for option in brief.get("diplomatic_options", []):
            alternatives.append({
                "kind": "diplomatic_option", "status": "conditional",
                "option": option,
                "scope": "relationship_to_recovery_unverified",
                "constraint": "Requires appropriate consent, timing and applicable fulfillment conditions.",
            })
    return deepcopy({
        "level": level,
        "closures": closures,
        "remaining_turns": brief.get("remaining_turns"),
        "alternatives": alternatives,
        "session_ended": complete,
        "novel_proposals": {
            "facilitator_initiative": GUIDANCE[level],
            "player_proposals_allowed": not complete,
            "mechanical_effects_require_validated_adjudication": True,
        },
        "assessment_limits": (
            "An ended session permits outcome assessment only." if complete else
            "Options are actor-visible submissions or conditional arrangements, not guaranteed recovery. "
            "A closed modeled route is not proof of global failure. No alternative listed is not proof of impossibility."
        ),
        "terminal_failure_established": False,
    })
