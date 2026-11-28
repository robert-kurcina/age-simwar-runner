# Grand tactical play — development plan

Status: author-directed concept, 2026-11-28. **Design only; implementation deferred.**
This is a third gameplay track, not a replacement for [strategic play](PLAN_STRATEGIC.md) or [narrative play](PLAN_NARRATIVE.md). [PLAN.md](PLAN.md) remains the common authority. Complete and qualify those engines independently before attempting cross-scale integration. AGE Enterprise remains out of scope.

## Purpose

Grand tactical play combines the personal agency of an embodied individual with the strategic agency of an office, organization or polity over which that individual exercises actual authority. The player experiences the making of history and the personal consequences of making it. Choices Matter at both scales.

The Great War is the preferred eventual proving ground. The author-proposed concept is the Embodiment of Sillis, the Grey Dragon, acting as an autarch. Periodic awakenings or interventions may be separated by years of regional change; significant encounters with other Deities or mortal individuals may occur at personal timescales. This is an experiential premise, not a newly established canonical chronology, roster, lifespan, domain rating or gameplay rule. Other historically appropriate embodiments may eventually be playable.

## Three gameplay modes

| Mode | Player agency | Temporal focus | Principal consequences |
|---|---|---|---|
| Narrative | Player-character's actions and interactions | Scenes and events | Personal, interpersonal, local |
| Strategic | Office or faction's policies, commitments and allocations | Time-skip between opportunities for intervention | Institutional, regional, civilizational |
| Grand tactical | Embodied character acting personally and through authorized institutions | Alternation between personal scenes and strategic intervals | Personal and collective consequences that inform one another |

Grand tactical is AGE's working gameplay term, not a claim about the conventional military meaning of grand tactics. A powerful character does not thereby own every institution, know every fact, or control every subject. Character identity, office, delegated authority, patronage, ownership and institutional consent remain distinct.

## Gameplay loop

1. Awaken or return to the situation at an appropriate decision epoch. Receive scoped reports of material changes since the previous intervention, including unresolved obligations and relevant personal history.
2. Assess regional conditions, competing faction interests, resource constraints, mortal welfare and personal relationships. Investigate uncertainty rather than assume omniscience.
3. Interact personally when the situation warrants it: conversation, negotiation, confrontation, discovery or other actions supported by the narrative engine. Preserve player ownership of the character's decisions and inner state.
4. Exercise institutional or divine authority through validated strategic commitments. Independent rulers, institutions, populations and rival Deities retain their own interests and capacity to refuse.
5. Resolve each action in its owning engine. Bridge only consequential, authorized outcomes through explicit, provenance-bearing records. No prose-only state mutation or automatic success at the other scale.
6. Advance to the next consequential intervention. During the interval, independent actors and scheduled or conditional developments continue to operate. Reconcile due commitments, losses, production, information receipt and relevant personal changes.
7. Present the new position, including human consequences, remembered promises, betrayals, unexpected developments and opportunities shaped by earlier choices. Conclude with earned personal and strategic outcomes.

Time skips can span minutes, hours, days, weeks, months, years or decades, according to the scenario's supported mechanics and meaningful decision opportunities. A long skip is not permission to freeze the rest of the world. The existing Great War strategic scenario remains eight quarterly Turns; a multi-year grand tactical scenario would be a separately bounded and source-reviewed experiment, not a silent change to that scenario.

## Consequential dimensions

- Personal: character identity, capabilities, physical condition, emotion, trust, loyalty, attachments, secrets, beliefs, promises, betrayals and remembered conduct. Reuse narrative mechanics, including the native Emotional state where appropriate; never assign the player's private feelings automatically.
- Strategic: population, poverty, starvation and food security, prosperity, production, consumption, trade, mobilization, armies, readiness, logistics, territorial security, institutions, legitimacy, religion, divine commitments and diplomatic relationships. Aggregate at the scale needed for meaningful management; do not simulate every person.
- Cross-scale: an interpersonal promise can motivate an institutional commitment but does not itself spend resources or establish authorized consent. A strategic decision can create personal circumstances, but does not prescribe an individual's feelings or response. Exceptional personal achievements may change strategic possibilities only through explicit adjudication.

Illustrative, noncanonical dilemma: an autarch is asked by a trusted ruler to divert resources from regional food security to military defense. A personal encounter may establish the ruler's request and the character's response. A strategic commitment may fund defense at a cost to other priorities. Later reports and encounters reveal what actually happened, including independent decisions, suffering, gratitude or resentment where supported. The outcome must emerge from play, not a predetermined dramatic arc.

## Temporal and authority boundaries

Treat the two existing engines as independent authorities in their own domains. Do not merge them into a monolith or build a universal simulator in anticipation of this mode.

For a future vertical slice, define a minimal, versioned cross-scale handoff using the common contracts in PLAN.md:

- Stable entity and event IDs, actual event time, source checkpoint/revision, scope, causal references and typed outcome.
- Explicit correspondence between an individual and the office or faction they may represent, including authority limits and changes of office or embodiment.
- One authoritative owner per consequential property and one application per accepted effect. No duplicate ledgers, automatic conversions or circular amplification.
- One coordinated chronology for the slice: define which interval is resolved, which events interrupt a skip, what remains pending, and whether an encounter is before or after strategic resolution. Never replay an elapsed interval twice.
- Actor-local projections. A personal encounter reveals only what its participants can know; institutional intelligence is not automatically available to an individual, nor are private thoughts automatically faction intelligence.
- Revision-bound validation, explicit accepted/rejected handoff, reproducible ordering, save/resume and replay. If a required rule or authorized mapping is missing, stop at the last valid state rather than invent an effect.
- Define death, loss of embodiment, loss of office and catastrophic failure before play. Preserve the narrative engine's existing terminal rules; do not imply resurrection, post-death play or automatic transfer to a successor. Any future embodiment-specific exception requires explicit author approval and source support.

These are design invariants, not a mandate for a shared database, new scheduler, generic event DSL or runtime rewrite. The first experiment should reuse the existing portable JSON/checkpoint and validated command boundaries.

## Ordered future roadmap

| Priority / status | Deliverable and exit criterion |
|---|---|
| P0 DEFERRED — prerequisite | Complete the independent Great War strategic cycle and narrative engine qualification; establish stable interfaces and actual evidence of relevant capabilities. |
| P1 DEFERRED | Select one bounded embodiment, region, dated interval and authority relationship. Pin sources, separate fixed canon from working hypotheses and approve the private scenario configuration. |
| P1 DEFERRED | Author one meaningful dilemma crossing both scales in each direction. Identify owning properties, the smallest accepted handoff and possible refusal/failure. Do not generalize beyond demonstrated need. |
| P1 DEFERRED | Prototype one complete personal encounter → strategic commitment → elapsed interval → personal consequence loop, preserving scoped knowledge, resource accounting and replay. |
| P1 DEFERRED | Qualify alternative outcomes, abstention, independent opposition, invalid authority, duplicate/stale handoffs, time-bound commitments, interruptions, save/resume and terminal failure. |
| P2 DEFERRED | Extend to a short multi-epoch embodied Great War rehearsal only if the prototype establishes value over playing either engine independently. |
| P3 OUT OF SCOPE | Universal cross-scale simulation, wider campaigns, full-stack integration and AGE Enterprise. |

## Acceptance

The mode is justified only if a player can recognize both the personal and collective costs of a decision, experience a later consequence that could not be adequately represented by either engine alone, and choose a credible alternative producing a different outcome without violating authority, time, visibility or resource invariants. A successful mechanical replay is necessary but not sufficient; player experiential review is required.

## Repository and source policy

All implementation and scenario ownership stay in age-simwar-runner. The canonical vaults are read-only pinned dependencies. This public plan records only the author-supplied conceptual premise and generic design; restricted historical details, hidden configurations and unapproved derived values belong in AGE's private staging or authorized delivery. No canonical changes are implied.

No implementation is authorized by this roadmap alone. Keep the two active development tracks independent, and do not reopen the Great War strategic closure scope to satisfy grand tactical requirements.
