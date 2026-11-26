# Development plan — playable, consistent games

## Goal

Run a complete scenario in one ordinary ChatGPT conversation, using either an authorized GitHub connector or an uploaded standalone ZIP. ChatGPT interprets decisions and presents narrative or staff briefings; the Python runtime validates and commits state. The same frozen scenario, engine revision, seed and resolved inputs must reproduce the same mechanical results across independent runs. Different player choices may produce different outcomes. Dialogue wording need not be identical.

Keep Python and JSON, existing strategic engine and narrative execution loop, and existing CLI entry points. Migrate narrative resolution to bounded DXD; reclassify Mythos-inspired content as Fear!. No new platform architecture unless actual gameplay exposes a concrete need. Supported execution remains bounded fictional investigation and civilian/institutional simulation; no operational military targeting or predictive claims.

## Status at reset (2026-11-26)

DONE on main: four public strategic fixtures, Boothbay trial, actor observations/objectives, resource accounting, scheduled events, time, checkpoint/replay, source compiler, campaign discovery, Chat launch guidance, runtime ZIP workflow, repository organization. PR #62 tests and bundle CI passed. PR #56 closed as superseded. Earlier private CI verified bounded recovery fixtures against pinned revisions; current-main private Chat gameplay and standalone upload need qualification.

DONE: PR #66 merged scenario/participant profiles; combined Tests 45801596447 and Chat runtime bundle 45801596576 passed. WIP milestone 1: Boothbay v4 binds active NPCs to native authored records, records encounters and earned disclosures, and uses authored Willpower for a provisional disclosure threshold adjustment. CI pending; v3 checkpoints require restart. Next: qualify actual play and extend to Castine rather than creating another participant engine.

PR #68 Castine trial remains open. Imported on main, not playable: Castine and Ram Island. WIP: bounded DXD Test kernel (not yet wired into gameplay); see [DXD migration](docs/dxd-migration.md). Private SH44SER/Conflagration packages pending; Sarna Len integration is not yet playable.

## NEXT — five milestones

| Milestone | Deliverable | Exit test |
|---|---|---|
| 1. Participants | Stable dated faction and NPC definitions, native attributes, motivations, resources, knowledge and relationships as relevant. Freeze these with scenario initialization. | Two independent runs start with identical participant records; bounded participant decisions obey recorded constraints. |
| 2. Events | Extend the existing scheduler with only the persistent conditions, milestones, dependencies and background changes required by a real scenario. Initialize prior history from reviewed dated conditions; advance eligible events when game time advances. | An ignored event still progresses; no duplicate effects; replay matches; alternate player choices affect only supported consequences. |
| 3. Geography and time | Stable location IDs, parent/route relationships and travel or reporting delays where they affect play; reuse existing maps and clocks. | Travel, event timing and visible map/observations agree; no contradictory locations or invented time advances. |
| 4. Scenario generation | Let ChatGPT propose a bounded configuration using existing supported rules. Validate, review and freeze it before play. Preserve unknowns and source dates. | A generated configuration launches through actual Python, rejects unsupported actions and reaches a meaningful end. |
| 5. Gameplay qualification | Complete narrative and strategic scenarios in ordinary Chat, including ZIP launch and authorized private content. | Same seed and resolved inputs replay exactly; different choices produce legitimate different results; player views do not disclose hidden state. |

Milestones are ordered by dependency, not separate infrastructure projects. Use a playable vertical slice for each increment. Prefer extending an existing module over adding a new abstraction. Stop adding mechanics when the selected scenario is sufficiently playable.

## Practical content queue

- First: implement the bounded DXD Test kernel, migrate Boothbay and Castine to Fear! with explicit character adaptations, then complete Ram Island using DXD. Do not port the entire DXD ruleset.
- In parallel where useful: use an existing civilian scenario to exercise participant behavior and persistent background events.
- Then qualify one authorized SH44SER recovery scenario in ordinary Chat; retain Conflagration inventory without claiming unsupported scenarios are playable.
- Add one bounded Sarna Len scenario only after useful source mappings and applicable DXD rules are established. Great War and Solo City are supporting sources, not additional engines to port.
- Distribute verified public standalone ZIP; produce private SH44SER and Conflagration-only packages when their supported content is ready. Keep private material out of public artifacts.

## Consistency contract

A scenario needs only six logical components: scenario metadata/objectives, participants, locations, events, rules and mutable session state. These may be ordinary JSON records in existing files. Separate fixed source facts from dated initialization, hypothetical assumptions and runtime changes. Preserve native units and unknown values. Use stable IDs, source revisions and explicit visibility. Persist a detail when it affects future decisions or continuity; purely descriptive prose need not be simulated.

Mechanical repeatability requires identical configuration, engine revision, seed and resolved inputs, including any model-proposed participant decisions. For independent runs without recorded model decisions, use bounded deterministic/seeded policies where required. Behavioral consistency means respecting motivations, capabilities and constraints, not producing identical dialogue.

Use vault-age as terminology/design reference, not an implementation checklist. Its Property Sheets map to existing JSON records; scope facets to scenario metadata; TickPolicy to existing clocks; event generators to bounded tables if needed; durable semantic facts to simple validated records. Source owners remain authoritative: SH44SER for its setting and native rules; current vault-sarnalen DXD for Sarna Len, Mai Appollonia Yo!, Apocalyptic Seizure!, and Fear!. Future SH44SER influence on DXD is deferred until the source rules change. Great War and Solo City supply applicable specialized material. Do not infer full DXD attributes from compressed MEST/Solo City values or back-project later national metrics.

## Verification and delivery

Run existing regression tests plus focused scenario tests; no new test framework. Demonstrate a full game before claiming playable. Test same-input replay, alternative decisions, independent perspectives, ignored events, repeated NPC encounters, resource exhaustion, and time-limit/early endings where supported. Confirm actual Python execution and actor-visible output; do not substitute generated prose for adjudication. Keep session files within the thread; cross-thread persistence is optional.

CI success is evidence of CI execution, not independent Chat play or private integration. Earlier local qualification claims in historical plans are retained as historical statements, not independently reverified in this reset.

## DEFERRED / NON-GOALS

Full AGE platform, universal rules DSL/AGEScript, full CAL/LMS-Graph, distributed partitions, PACE, Storygen integration, autonomous multi-agent platform, continuous global simulation, databases, microservices, multiplayer branching, hosted browser/MCP, exhaustive geographic or historical calibration, full native ruleset ports, mandatory cross-thread persistence. Existing optional interfaces remain intact; no further work unless a demonstrated gameplay need warrants it.

## History

Previous detailed plan remains available at [the pinned pre-reset revision](https://github.com/robert-kurcina/age-simwar-runner/blob/f7d9dba6dcc3db29b3c1c2eb0c36224c10f3e5ef/PLAN.md). Architecture references: [ADR-001](docs/adr/001-canonical-source-references.md), [vault-age](https://github.com/robert-kurcina/vault-age/tree/ed080124bb28a3ebb65b80eadbadfb4420de4f73). Update this plan only when milestones, evidence or priorities change.
