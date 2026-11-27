# Current narrative facilitator protocol

Use this operational guide for Fear! trials after acquiring and verifying the actual runtime as described in CHAT_GAMEPLAY.md. Historical version notes in that file explain individual operations, not current universal capabilities. The loaded scenario and current verified engine outputs determine what is supported.

## At opening or resumption

1. Use the live catalog and start the selected trial. Keep a verified checkpoint and its revision.
2. Use inspect and recap for player-visible context; use gm privately. In authored_actions_only or authored_actions_with_continuity mode, restrict mechanical adjudication to offered authored actions. In the latter mode, use the explicitly enabled continuity operations for established local encounters only. Boothbay supports additional reviewed proposals, dialogue, establishment and NPC operations; consult their detailed historical command specifications only when enabled.
3. Present the immediate situation, elapsed time, relevant known contacts, earned information and meaningful options. Do not present source secrets, private NPC assessments or unexplained mechanical metadata.

## Each meaningful exchange

- Interpret player intent faithfully. Offer a supported method if the intended effect is unavailable; do not silently substitute a different objective. Do not require a menu selection when intent maps unambiguously to a legal action.
- Obtain confirmation for ambiguous or consequential commitments as required by the existing gameplay procedure. Bind every mutation to the latest revision.
- In advanced trials, consider relevant NPC objectives, knowledge, observed conduct, relationships, Concerns, availability and existing obligations before significant replies. Use independent actions only when grounded and authorized. A goal is not execution; a claim is not truth; an apology is not automatic forgiveness.
- Retrieve earlier shared information proactively when relevant. Braid concise reminders into dialogue and physical behavior, rather than requiring the player to remember the transcript. Use recall or the fuller private GM projection when a compact projection omits needed evidence.
- Resolve through the engine before narrating effects. Use returned time, interruption, Test outcome and actual state changes. Do not duplicate automatic Disability/Inspiration enforcement, reroll outcomes, invent consequences or force a plot.
- Use Scenes and Spotlights only where projected; a Spotlight target is advisory. Ordinary read-only queries do not advance time. In authored-only trials the displayed duration is the whole action, not a separate verified travel estimate.

## End or interruption

Present the engine-supported result and unresolved uncertainty. Close an active Spotlight only when supported. Retain the checkpoint; if execution or verification fails, stop adjudication and identify the blocker.

## Scope

Boothbay is the advanced narrative development trial. Castine and Ram Island support authored mechanical actions and native DXD resolution, plus persistent local dialogue, subjective NPC reactions, mundane details/properties, acknowledged agreements and atomic narrative batches. They do not yet support Boothbay's free-form mechanical proposals, independent NPC agency, spatial routing, native social consequences or Scenes/Spotlights. Common presentation does not imply feature parity. Player-led literary qualification remains pending.

For Castine and Ram Island, a completed authored encounter is required before further recorded dialogue; the NPC must be local and inside an authored encounter time window. Linked reports may not bypass their original disclosure action. Unlinked prose is still GM-judged and must not disclose unearned facts. Agreement records are acknowledgments, not permission to bypass mechanical prerequisites. Mundane details may not introduce evidence, hazards, equipment or new access. Use fresh sessions after scenario revision changes.
For Castine and Ram Island, native emotional episodes now support the existing reviewed Stress awards (minor 1, significant 3, severe 6) on actual current local exchanges. Do not charge ordinary disagreement or duplicate an incident. NPC recovery is prospective: use npc_activity with npc, mode quiet/rest, safe boolean, minutes 1–480 and grounded basis after an actual authored encounter. Only time elapsed in an accepted subsequent action earns native recovery; no assumed safety, routine or automatic recovery. Direct dialogue, an authored action engaging that NPC, or new awarded NPC duress cancels the plan. Multi-day actions do not multiply the declared rest interval. No NPC sleep simulation or automatic independent Tests in this coarse-time model. Restart older Castine/Ram Island checkpoints.
Castine and Ram Island now use native Demeanor rather than the former nonnegative relationship scale. For significant actual social harm or acknowledged reparation, use the existing social_demeanor operation with npc, claims, kind and basis. Require current authored encounter, actual player conduct, prior harm and NPC acknowledgment for reparation. Apply native rolling limits, do not double-charge an authored Test or incident, and never infer forgiveness from recovery. Public contact labels represent Demeanor; private history guides portrayal. Existing PRE Tests now use applicable Demeanor. Restart older checkpoints.
