# Development plan — playable, consistent games

## Goal

Play a complete game in one ordinary ChatGPT conversation, from authorized GitHub sources or an uploaded standalone ZIP. ChatGPT interprets decisions and presents results; Python validates and commits state. Frozen configuration, engine revision, seed and recorded inputs must replay exactly.

Keep Python, JSON and existing CLI entry points. Favor playable vertical slices over infrastructure. Add a property or mechanic only when it changes a meaningful game decision, consequence or continuity requirement.

## Status — 2026-11-26

- DONE: deterministic clock, actor views and objectives, resource accounting, scheduled events, checkpoints/replay, source compiler, participant profile compiler, campaign catalog and selected scalar continuity.
- DONE: four short public civic fixtures; PR #80 adds one-shot conditional institutional events with visible prerequisites, guarded debits and recorded outcomes.
- DONE: Fear! Boothbay v15, Castine v8 and Ram Island v3, shared bounded DXD, derived Attributes, Concerns, Favor, Inspiration, Morale and Psychology. PR #78 tests and bundle CI passed (45814058341, 45814058241). Player-led Boothbay Chat trial completed with negative gameplay feedback; execution verified, experiential qualification WIP. PR #79 inline icons merged. See [DXD migration](docs/dxd-migration.md).
- WIP: substantial strategic gameplay and current private SH44SER recovery qualification. Public runtime ZIP workflow exists; private SH44SER and Conflagration packages pending.
- PENDING: first bounded Sarna Len scenario.

## Gameplay tracks and immediate priorities

- [Narrative game plan](PLAN_NARRATIVE.md): immediate Boothbay gameplay correction and qualification; then other Fear! scenarios.
- [Strategic game plan](PLAN_STRATEGIC.md): preserve existing faction-based SH44SER recovery roadmap and qualify substantial strategic play independently.

Maintain one shared engine and delivery path, with separate gameplay acceptance criteria. Neither track requires mechanics specific to the other. Prioritize the Boothbay vertical slice in the next implementation cycle; strategic work remains WIP, not cancelled. Record actual player feedback separately from deterministic execution and CI results.

## Consistency and verification

Reuse existing JSON records: scenario metadata/objectives, factions or narrative participants, locations, events, rules and session state. Resources, projects and relationships may be simple properties; separate records only when necessary. Persist what affects future decisions. Preserve stable IDs, source revisions, visibility, relevant reporting delays and deterministic order. Record model-proposed decisions as resolved inputs. Use existing tests and actual gameplay, not generated narration as proof. CI alone does not qualify independent Chat play. Keep private content out of public archives.

Source authority: SH44SER uses its native system; vault-sarnalen DXD governs Sarna Len, Mai Appollonia Yo!, Apocalyptic Seizure! and Fear!. Use vault-age as terminology and design reference, not a mandatory architecture. Keep historical equipment vocabulary deferred until needed; the modern `meta-dxd` draft (`a9dd1966a4a3d68db9595209c82c3664354d9176`) is a working reference, not accepted canon.

## Deferred / non-goals

No mandatory SH44SER corpus expansion, universal property catalog, exhaustive inventories, individual-agent simulation, global economic simulation, full ruleset ports, formal standards compliance, universal DSL, full CAL/LMS-Graph, distributed partitions, PACE or Storygen integration, databases, microservices, multiplayer, hosted browser/MCP, mandatory cross-thread persistence or operational military targeting. Supported execution remains bounded fictional investigation and civilian/institutional simulation, not predictive claims. Add mechanics only when a demonstrated gameplay need warrants them.

## History

[Previous plan](https://github.com/robert-kurcina/age-simwar-runner/blob/9c0b0c5bb9f10893c7bfa71fe7ac48823d0ff283/PLAN.md) preserves earlier milestones and verification history. [ADR-001](docs/adr/001-canonical-source-references.md). Update this plan only when milestones, evidence or priorities change.
