# Strategic game development plan

Status: WIP (P1) — 2026-11-26. Shared constraints, priority levels, status vocabulary and final full-stack gate: [master plan](PLAN.md). Keep this track's ordered deliverables current using DONE, WIP, NEXT, PENDING, BLOCKED, DEFERRED and REJECTED; attach exit evidence to completed work. Full-stack service work is DEFERRED (P3) and belongs at the end of the master plan, not in this track.

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
| 1 | DONE (PR #82, CI passed): optional dated organization context bound to existing actors using the participant compiler; no duplicate mutable stocks. Fiji pilot needs only its existing relief objective, aid resources and dated history. | Faction context and authority are consistent; no invented canon or individual-agent model. |
| 2 | DONE (PR #83, both CI workflows passed): native Shortfall bands and bounded weekly project progression using existing state and ledger; deterministic delay policy, no character tests. | A project can progress, stall or change scope; resource guards and replay hold. |
| 3 | DONE (PRs #85–86, CI passed): funded capacity decisions and actor-local model choice/abstention. Private adapter now wired; live model qualification pending. | Unsupported effects are rejected; independent decisions and ignored events remain consistent. |
| 4 | DONE (mechanical): 12-week illustrative Fiji scenario and scripted alternatives passed on vault #993 (run 45873529443), including exact replay, visibility and independent partner abstention. WIP (P1): actual strategic Chat gameplay and live model choices. Preserve original pilot. | Complete actual Chat play with alternative outcomes and exact replay. |
| 5 | PENDING (P2): Carry forward only consequential faction conditions, commitments and resources into a successor scenario; qualify reviewed scenario generation and public/private ZIP delivery. | Meaningful campaign continuity, frozen configuration, correct visibility and verified execution. |

Keep existing civic fixtures for regression. Do not build another generic campaign before the SH44SER vertical slice unless a concrete test requires it. Conflagration inventory remains partial; qualify supported civilian/institutional content only. Add bounded Sarna Len content later using native DXD. Great War and Solo City are supporting sources, not additional engines to port.

## Gameplay qualification

A strategic turn must present a changed situation, meaningful faction-level alternatives, opportunity costs and observable consequences. Use existing actor views, conditional events and accounting before adding mechanics. At least two plausible strategies must produce materially different intermediate states and outcomes; independent factions or scheduled developments must matter even when ignored. Show commitments, bottlenecks, uncertainties and decision-relevant geography. Do not import narrative character mechanics or require SH44SER corpus expansion. Qualify one authorized recovery slice before broadening content; distinguish actual play evidence from CI.

## Repository ownership correction — 2026-11-26

- DONE: audit of vault-sh44ser SimWar PRs #977–#993 and repository boundaries. Public runner already contains generic private play, source compilation, project economy, faction decisions and regression tests; do not duplicate these.
- DONE: runner #89 migration safeguards and public CI; vault #993 scripted strategic qualification (export failed separately), #994 export correction merged.
- WIP (P1): qualify corrected export and establish durable authorized private versioned scenario access. The earlier local-only migration procedure is superseded in that respect: a Mac-local copy is optional, not an architectural dependency. Decide private companion repository versus private runner before migration; neither is authorized by this plan alone.
- BLOCKED: vault cleanup until complete, byte-verified private retention and replacement execution are confirmed. Never copy private content into public commits or bundles.
- REJECTED: mandatory local-only private scenario storage for Chat-first gameplay.
