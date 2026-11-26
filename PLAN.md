# Development plan — playable, consistent games

## Goal

Play a complete game in one ordinary ChatGPT conversation, from authorized GitHub sources or an uploaded standalone ZIP. ChatGPT interprets decisions and presents results; Python validates and commits state. Frozen configuration, engine revision, seed and recorded inputs must replay exactly.

Keep Python, JSON and existing CLI entry points. Favor playable vertical slices over infrastructure. Add a property or mechanic only when it changes a meaningful game decision, consequence or continuity requirement.

## Status — 2026-11-26

- DONE: deterministic clock, actor views and objectives, resource accounting, scheduled events, checkpoints/replay, source compiler, participant profile compiler, campaign catalog and selected scalar continuity.
- DONE: four short public civic fixtures; PR #80 adds one-shot conditional institutional events with visible prerequisites, guarded debits and recorded outcomes.
- DONE: Fear! Boothbay v15, Castine v8 and Ram Island v3, shared bounded DXD, derived Attributes, Concerns, Favor, Inspiration, Morale and Psychology. PR #78 tests and bundle CI passed (45814058341, 45814058241). Player-led Chat trial underway; feedback separately. PR #79 inline icons merged. See [DXD migration](docs/dxd-migration.md).
- WIP: substantial strategic gameplay and current private SH44SER recovery qualification. Public runtime ZIP workflow exists; private SH44SER and Conflagration packages pending.
- PENDING: first bounded Sarna Len scenario.

## Strategic design

The unit of play is the faction, not the individual person. Leaders, figureheads, constituent institutions and internal friction are qualitative context unless independently consequential; do not generate character sheets or simulate their members. The LLM represents faction interests and proposes decisions; the engine validates supported effects, authority, resources, timing and information boundaries. No unrecorded model state changes.

Use existing SH44SER simple native properties and descriptions, without requiring expansion of its corpus. The National Database is the 2044 baseline, not a 2003 snapshot. Use dated local history for earlier scenarios. Preserve units, ranges and unknowns; distinguish canonical facts, native derivations, reviewed scenario assumptions and runtime changes. Do not invent canonical values or convert GDP into available treasury funds.

Use native Economy Design where applicable: select only one to three relevant capacity axes per project Turn (0–5), compare Project Need (1–5), select the largest Shortfall, and resolve the supported consequence or applicable native Test. Track the bottleneck and meaningful progress, not every shipment or axis. Do not invent universal faction ratings, duplicate native logistics rules, or port character mechanics into faction play.

Source reference (pinned audit revision `2700b3939d13df4811f8b8565e753c6f8143a5e6`):
- [National Database](https://github.com/robert-kurcina/vault-sh44ser/blob/2700b3939d13df4811f8b8565e753c6f8143a5e6/04_Global_Order/02_Blocs_Regions/02_National_Database.md)
- [Economy Design Core](https://github.com/robert-kurcina/vault-sh44ser/blob/2700b3939d13df4811f8b8565e753c6f8143a5e6/12_Game_System/08_Advanced_Design/20_Economy_Design/02_Design_Core.md)
- [Logistics and Shipping](https://github.com/robert-kurcina/vault-sh44ser/blob/2700b3939d13df4811f8b8565e753c6f8143a5e6/12_Game_System/08_Advanced_Design/20_Economy_Design/12_Logistics_Shipping.md)

External standards are optional semantic references, not required schemas: W3C ORG/PROV, BPMN/DMN, stock-and-flow accounting, NIMS/SCOR, GeoJSON and SISO scenario guidance. Reuse useful conventions only; no compliance or new standards subsystem.

## NEXT — lean implementation sequence

| Step | Deliverable | Exit test |
|---|---|---|
| 1 | WIP: optional dated organization context bound to existing actors using the participant compiler; no duplicate mutable stocks. Fiji pilot needs only its existing relief objective, aid resources and dated history. | Faction context and authority are consistent; no invented canon or individual-agent model. |
| 2 | Implement the bounded native Economy Design bottleneck procedure and necessary persistent consequences using existing events and accounting. | A project can progress, stall or change scope; resource guards and replay hold. |
| 3 | Support constrained LLM-proposed faction decisions, preserving exact accepted inputs. | Unsupported effects are rejected; independent decisions and ignored events remain consistent. |
| 4 | Extend one authorized SH44SER civilian recovery scenario into a substantial strategic game; add location, timing and reporting details only where needed. Target 12–24 Turns if useful, not a quota. | Complete actual Chat play with alternative outcomes and exact replay. |
| 5 | Carry forward only consequential faction conditions, commitments and resources into a successor scenario; qualify reviewed scenario generation and public/private ZIP delivery. | Meaningful campaign continuity, frozen configuration, correct visibility and verified execution. |

Keep existing civic fixtures for regression. Do not build another generic campaign before the SH44SER vertical slice unless a concrete test requires it. Conflagration inventory remains partial; qualify supported civilian/institutional content only. Add bounded Sarna Len content later using native DXD. Great War and Solo City are supporting sources, not additional engines to port.

## Consistency and verification

Reuse existing JSON records: scenario metadata/objectives, factions or narrative participants, locations, events, rules and session state. Resources, projects and relationships may be simple properties; separate records only when necessary. Persist what affects future decisions. Preserve stable IDs, source revisions, visibility, relevant reporting delays and deterministic order. Record model-proposed decisions as resolved inputs. Use existing tests and actual gameplay, not generated narration as proof. CI alone does not qualify independent Chat play. Keep private content out of public archives.

Source authority: SH44SER uses its native system; vault-sarnalen DXD governs Sarna Len, Mai Appollonia Yo!, Apocalyptic Seizure! and Fear!. Use vault-age as terminology and design reference, not a mandatory architecture. Keep historical equipment vocabulary deferred until needed; the modern `meta-dxd` draft (`a9dd1966a4a3d68db9595209c82c3664354d9176`) is a working reference, not accepted canon.

## Deferred / non-goals

No mandatory SH44SER corpus expansion, universal property catalog, exhaustive inventories, individual-agent simulation, global economic simulation, full ruleset ports, formal standards compliance, universal DSL, full CAL/LMS-Graph, distributed partitions, PACE or Storygen integration, databases, microservices, multiplayer, hosted browser/MCP, mandatory cross-thread persistence or operational military targeting. Supported execution remains bounded fictional investigation and civilian/institutional simulation, not predictive claims. Add mechanics only when a demonstrated gameplay need warrants them.

## History

[Previous plan](https://github.com/robert-kurcina/age-simwar-runner/blob/9c0b0c5bb9f10893c7bfa71fe7ac48823d0ff283/PLAN.md) preserves earlier milestones and verification history. [ADR-001](docs/adr/001-canonical-source-references.md). Update this plan only when milestones, evidence or priorities change.
