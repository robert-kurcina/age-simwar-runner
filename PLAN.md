# Development plan — playable, consistent games

## Purpose — AGE experimental testbed

AGE SimWar Runner is a bounded executable testbed for Amazing Game Engine (AGE), not the definitive AGE implementation. Develop playable games to test, refine, reject or validate AGE concepts through actual use. Reuse applicable lightweight Property Sheets, stable IDs, scope facets, TickPolicy, Location/Event Sheets, simplified Event Generators and authoritative state semantics where useful; do not implement full AGE subsystems merely for architectural conformity. Record reusable findings, counterexamples and limitations in the existing plans or architecture notes, and propose upstream AGE changes separately when evidence warrants them. A successful runner experiment is evidence, not automatic adoption into AGE.

**AGE Enterprise is an entirely separate, future effort.** It is outside the scope of this project and is not a deferred SimWar deliverable. Neither the ChatGPT runtime nor the eventual full-stack SimWar service constitutes an AGE Enterprise implementation. Testbed findings may inform that future effort, but its architecture, roadmap, requirements and implementation must be established independently. Do not introduce Enterprise requirements into SimWar or treat the testbed's completion as Enterprise acceptance.

## Goal

Play a complete game in one ordinary ChatGPT conversation, from authorized GitHub sources or an uploaded standalone ZIP. ChatGPT interprets decisions and presents results; Python validates and commits state. Frozen configuration, engine revision, seed and recorded inputs must replay exactly.

Keep Python, JSON and existing CLI entry points. Favor playable vertical slices over infrastructure. Add a property or mechanic only when it changes a meaningful game decision, consequence or continuity requirement.

## Shared game-length design

Author-approved game-length targets are 6 (Short), 12 (Standard) or 24 (Extended) consequential player decisions: Critical Decisions in strategic play and Spot-lights in narrative play. Narrative scenes and strategic simulation Turns are distinct from these pacing units. Intermediate actions, reading, clarification, mechanical resolution and autonomous developments do not automatically consume a player's decision budget. The 20-decision target is superseded; retain historical evidence and legacy fixture durations until deliberately adapted. Do not equate LLM exchanges or elapsed fictional time with the pacing budget. Each gameplay track owns its terminology and implementation.

## Shared consequential information and world establishment

Author direction (2026-11-27): share applicable implementation concepts across strategic and narrative gameplay. This section is the common design authority; track plans own domain-specific sequencing and evidence. Existing implementations are pilots, not proof that a shared API already exists.

### Common semantic contracts

| Concern | Shared invariant | Domain-specific interpretation |
|---|---|---|
| Objective state | Canon, reviewed opening assumptions and committed runtime facts remain distinguishable; reference existing authoritative properties rather than duplicating them. | Character/location/object state versus faction/infrastructure/resource state. |
| Communication | Stable material claim ID, speaker, explicit recipients, time, scope, proposition reference when available, causal/source references; retain corrections and contradictions without rewriting history. | Dialogue/disclosure versus diplomatic statement, report or intelligence exchange. |
| Epistemic state | Receipt, access, belief, suspicion, inference, stale information and speaker intent are distinct. No automatic propagation, belief, truth promotion or inferred player inner state. | NPC knowledge/stance versus faction intelligence/assessment. |
| Establishment | Referee may propose scoped, plausible new session facts under delegated authority; distinguish descriptions from consequential effects. Stable IDs, provenance, visibility, prior-value guards for changes. No canon edits or unearned evidence/resources/authority. | Local objects and details versus administrative bodies, facilities, reports or circumstances. |
| Commitments and permissions | Separate statement, intent, offer, authorized consent, active obligation/permission, fulfillment, refusal, expiry and revocation where supported. Consent must come from the actual authorized actor, not a model assertion on its behalf. | Custody/access/Keys versus grants, treaties, inspections and institutional obligations. |
| Consequential developments | Typed prerequisites, authorized effects, eligibility, timing, visibility and one-shot/idempotence rules where applicable. Event creation is not event fulfillment. | DXD Clocks/Locks/Triggers/Events versus strategic conditional developments and deadlines. |
| Persistence | One authoritative checkpoint/history per session; derive projections, current assertions and relationship history from recorded inputs and existing state. Exact mechanical replay does not require regenerating prose. | Preserve native time, RNG, pacing and mechanics in each track. |

Use a common two-pass interaction process: retrieve actor-scoped facts and relevant history; formulate proposed communication or developments; extract and classify consequential content; validate against current revision, actual authority, provenance, visibility and preconditions; commit atomically; reconcile with committed results before presenting. Do not advance time, consume RNG or change state for rejected batches or purely informational exchanges unless a native rule explicitly requires it. Free-text semantic truth and actual consent cannot be proven by structural validation; the referee must check grounding and the player's actual words. Persist only material information, not every utterance. Do not silently repair missing records by retconning established facts.

### Shared implementation coordination

| Workstream | Initial implementation lead | Reuse and acceptance |
|---|---|---|
| Claim/proposition identity, receipts, stance and scoped history | Narrative (existing v44–v46 pilots) | Strategic adapts faction reports and beliefs; extract small common helpers only after both use cases demonstrate compatible semantics. |
| Scoped establishment, entity properties and prior-state guards | Narrative (v47–v49 pilots) | Strategic adapts non-canonical descriptive facts; domain adapters own eligibility and material effects. |
| Consent, permissions, commitment lifecycle | Joint; strategic existing agreement/negotiation and narrative custody/permission pilots | Share authority/lifecycle validation where compatible, not domain resource or DXD adjudication. |
| Conditional developments, Event Generator and scheduling | Joint; strategic owns isolated generator qualification, narrative owns native clock/trigger integration | Compare existing event/predicate paths first; reuse typed guards/provenance, not a universal scheduler or effect DSL. |
| Revision-bound transactions, scoped projections, replay, persistence | Joint, existing core runtime | Share proven utilities, preserve versioned checkpoint compatibility or explicit migration/restart guidance. |

Each track must inspect the other track's current implementation and this contract before adding overlapping capability. Name the first adopter and intended second adopter in its PR; distinguish shared candidate, implemented in one track, reused by both, and qualified by both. For shared changes, include representative regression coverage for both modes or record the second adopter as pending; no claim of common qualification from one track alone. Coordinate overlapping files and use small coherent PRs; neither track waits for a universal abstraction. Avoid duplicate authoritative stores, speculative framework extraction, mandatory schema migration, general ontology, or new database. Retain portable JSON and existing read/save boundaries; defer SQLite or other storage until the full-stack gate or measured need. Record compatibility and known semantic limits in the relevant plans.

Priority: existing release blockers and narrative P0 experiential work retain precedence; strategic P1 information/interaction vertical slice runs alongside source compilation and roster work. Shared contract work is PENDING until implemented and qualified; existing pilot evidence remains in track plans. No new upstream canon or AGE Enterprise scope.

## Priority and status discipline

Use this master plan as the shared priority authority; PLAN_STRATEGIC.md and PLAN_NARRATIVE.md maintain their own ordered deliverables and evidence. Keep one shared engine. Apply the following vocabulary in all three plans:

| Status | Meaning |
|---|---|
| DONE | Deliverable meets its stated exit criteria; record evidence (PR, test, actual play or author acceptance as applicable). |
| WIP | Actively being implemented or qualified; state remaining exit criteria. |
| NEXT | Highest-priority ready work in the relevant track; promote to WIP when started. |
| PENDING | Accepted backlog item, not yet selected. |
| BLOCKED | Cannot proceed until a named dependency or decision is resolved. |
| DEFERRED | Deliberately postponed until a stated gate or demonstrated need; not active work. |
| REJECTED | Explicitly declined approach or scope; record rationale, reconsider only with new evidence or author direction. |

Priority is independent of status: P0 = release/qualification blockers; P1 = current playable vertical slices; P2 = subsequent accepted gameplay improvements; P3 = deferred post-qualification delivery. Within a priority, dependencies and demonstrated gameplay value determine order. Keep WIP small, use the existing two track plans rather than a new tracker, and update status/evidence at each meaningful checkpoint. Do not mark gameplay DONE merely because a PR merged or CI passed. Split implementation, mechanical verification and experiential acceptance when their statuses differ. A blocked task does not prevent independent work. Avoid promoting deferred infrastructure ahead of the Chat gameplay gate.

## Status — 2026-11-26

- DONE: deterministic clock, actor views and objectives, resource accounting, scheduled events, checkpoints/replay, source compiler, participant profile compiler, campaign catalog and selected scalar continuity.
- DONE: four short public civic fixtures; PR #80 adds one-shot conditional institutional events with visible prerequisites, guarded debits and recorded outcomes.
- DONE: Fear! Boothbay v15, Castine v8 and Ram Island v3, shared bounded DXD, derived Attributes, Concerns, Favor, Inspiration, Morale and Psychology. PR #78 tests and bundle CI passed (45814058341, 45814058241). Player-led Boothbay Chat trial completed with negative gameplay feedback; execution verified, experiential qualification WIP. PR #79 inline icons merged. See [DXD migration](docs/dxd-migration.md).
- DONE: scripted Fiji 12-turn strategic alternatives, resource guards, actor visibility and exact replay (vault-sh44ser #993, run 45873529443; export step failed separately).
- DONE (mechanical): strategic decision support and one-turn resolution (#97), connector source adapter (#99), Critical Decision pacing (#102; CI 45881735000/45881734972), and actual private portable scenario qualification (vault #995, run 45882376581, artifact 15147307624). Fiji is a mechanical regression fixture, not the standard consim design.
- DONE (mechanical): strategic cooperation and negotiation (#124, #126), consequential diplomatic decisions (#127), and bounded same-project strategic continuity (#131; Tests 45902970747 and bundle 45902970730).
- NEXT (P1 strategic): establish dated faction configurations across the eight verified Conflagration campaign groups, recover the previously approved roster, and prioritize representative scenario content over generic engine expansion. Keep historical phase, player perspective and hypothetical variations distinct. See [strategic plan](PLAN_STRATEGIC.md).
- WIP (P1): strategic experiential qualification (author-led testing deferred at author request) and dependency ownership migration. Keep private material in authorized storage; migrate generic SimWar-specific tools out of SH44SER only after a verified replacement. Do not expand mechanics merely to hit a decision quota.
- DEFERRED (P2): first bounded Sarna Len scenario, until the narrative foundation is qualified.

## Development phases and immediate priorities

| Phase | Status | Purpose |
|---|---|---|
| Shared foundation | DONE for existing verified capabilities; WIP for demonstrated gaps | Shared authoritative runtime, source bindings, replay and delivery. Evolve as gameplay experiments require. |
| [Narrative sub-game](PLAN_NARRATIVE.md) | WIP (P1) | GM-directed, character-scale gameplay; qualify Boothbay, then other Fear! scenarios. |
| [Strategic sub-game](PLAN_STRATEGIC.md) | WIP (P1) | Faction-scale gameplay; establish phase-specific Conflagration factions and qualify meaningful independent faction decisions. |
| Full-stack service | DEFERRED (P3) | Final experimental phase; see the last section of this plan. |

Narrative and strategic phases run concurrently, not sequentially. Each has its own plan, priorities and acceptance criteria; neither must wait for the other to finish. Both exercise one shared engine and feed lessons back into AGE. Coordinate changes to shared contracts and regression-test both modes when affected. Prioritize the smallest useful vertical slices independently; shared blockers take precedence when they actually impede play. ChatGPT gameplay acceptance is the joint exit gate of these concurrent phases, not a separate infrastructure project. Record actual player feedback separately from deterministic execution and CI results.

## Consistency and verification

Reuse existing JSON records: scenario metadata/objectives, factions or narrative participants, locations, events, rules and session state. Resources, projects and relationships may be simple properties; separate records only when necessary. Persist what affects future decisions. Preserve stable IDs, source revisions, visibility, relevant reporting delays and deterministic order. Record model-proposed decisions as resolved inputs. Use existing tests and actual gameplay, not generated narration as proof. CI alone does not qualify independent Chat play. Keep private content out of public archives.

Content dependency direction: `age-simwar-runner` consumes `robert-kurcina/vault-sh44ser` as an explicit versioned, read-only content dependency for SH44SER games. SH44SER does not depend on SimWar. Resolve exact commit/path bindings through the existing source compiler and authorized connector or Git checkout. Other settings retain their own source dependencies. SimWar-owned scenario definitions, adapters, qualification and packaging belong to SimWar; retain private scenario data only in authorized private storage. Do not embed private canon in public bundles or require a local checkout.

Source authority: SH44SER uses its native system; vault-sarnalen DXD governs Sarna Len, Mai Appollonia Yo!, Apocalyptic Seizure! and Fear!. Use vault-age as the broader AGE design reference and potential recipient of validated testbed findings, not a mandatory implementation architecture. Keep historical equipment vocabulary deferred until needed; the modern `meta-dxd` draft (`a9dd1966a4a3d68db9595209c82c3664354d9176`) is a working reference, not accepted canon.

## Deferred / rejected scope

- DEFERRED: databases, service hosting, browser/MCP integration, multiplayer and cross-thread persistence unless justified by the final delivery phase or a demonstrated requirement. No commitment to any particular infrastructure.
- REJECTED for current scope: mandatory SH44SER corpus expansion, universal property catalog, exhaustive inventories, individual-agent simulation, global economic simulation, full ruleset ports, formal standards compliance, universal DSL, full CAL/LMS-Graph, distributed partitions, mandatory PACE or Storygen integration, and operational military targeting. Supported execution remains bounded fictional investigation and civilian/institutional simulation, not predictive claims. Add mechanics only when a demonstrated gameplay need warrants them.

## History

[Previous plan](https://github.com/robert-kurcina/age-simwar-runner/blob/9c0b0c5bb9f10893c7bfa71fe7ac48823d0ff283/PLAN.md) preserves earlier milestones and verification history. [ADR-001](docs/adr/001-canonical-source-references.md). Update this plan at meaningful development checkpoints when status, milestones, evidence or priorities change.

## Final testbed phase — full-stack service (DEFERRED, P3; last)

**Entry gate:** The author confirms that AGE SimWar is runnable to satisfaction entirely within ordinary ChatGPT, with both strategic and narrative gameplay qualified, authorized scenario selection, meaningful decisions and consequences, native rule fidelity, correct visibility, completion/resumption and reproducible mechanical replay. CI alone cannot satisfy this gate.

Only after this gate and resolution of outstanding accepted Chat-first project work, begin the full-stack service phase to test the same engine and scenario packages in a service delivery context. This is another AGE testbed phase, not an undertaking to implement the complete AGE platform or AGE Enterprise. AGE Enterprise remains an independent future project; completing this service completes only the SimWar testbed's final phase. Define the smallest useful client/server delivery architecture at that time, including a service interface, browser client, session persistence, authorization for private content, deployment and end-to-end verification as warranted. Reuse the existing authoritative engine; do not fork adjudication or introduce a mandatory server dependency into Chat play. Select hosting, database, authentication and deployment technologies only against demonstrated service requirements. Multiplayer and other optional expansions are not implied.

**Exit gate:** The service can start, play, resume and complete qualified scenarios with the same validated mechanics, information boundaries and replay behavior as ChatGPT, and the author accepts the service. No full-stack implementation before the entry gate.
