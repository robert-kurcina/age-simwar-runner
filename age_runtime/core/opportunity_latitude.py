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
