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
        "objective_outcomes": brief.get("objective_outcomes", {}),
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


def objective_outcomes(definitions, observed, reports, projects, minute, end_minute, turn_minutes):
    """Conservative goal classification from own observations, never hidden values.

    Project progress is monotone and increases at most once per resolution.
    Only directly bound progress thresholds receive an early impossibility proof.
    Other variables may change by mechanisms not represented in the local brief.
    """
    remaining = (max(0, end_minute - minute) + turn_minutes - 1) // turn_minutes
    ended = minute >= end_minute
    by_progress = {p["progress"]: p for p in projects}
    result = {}
    for ident, definition in definitions.items():
        key = definition["key"]
        report = reports.get(key, {})
        observation = observed.get(ident)
        record = {"description": definition["description"], "status": "unconfirmed",
                  "terminal": ended}
        if observation is None or report.get("status") != "current":
            record["basis"] = "No current actor-visible report; do not infer final outcome."
        elif ended:
            record.update(status="achieved" if observation["met"] else "objective_failure",
                          basis="Current report at configured scenario end.")
        else:
            project = by_progress.get(key)
            actual = observation["actual"]
            threshold = definition["threshold"]
            comparison = definition["comparison"]
            if project is not None:
                ceiling = min(project["stages"], actual + remaining)
                record["modeled_range"] = {"minimum": actual, "maximum": ceiling}
                impossible = ((comparison in ("at_least", "equal") and threshold > ceiling)
                              or (comparison in ("at_most", "equal") and threshold < actual))
                if impossible:
                    record.update(status="objective_failure",
                                  basis="Threshold outside proven modeled project progress bounds.")
            if record["status"] != "objective_failure":
                record.update(status="currently_met" if observation["met"] else "open",
                              basis="Current report; final outcome not yet established.")
        result[ident] = record
    return result
