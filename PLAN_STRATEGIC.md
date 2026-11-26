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

## Content dependency and ownership

Author-approved: `robert-kurcina/vault-sh44ser` is a versioned, read-only content dependency of `age-simwar-runner` for SH44SER scenarios. The engine consumes exact canonical revision/path references through its existing compiler. SH44SER has no reverse dependency on SimWar; scenario configuration, qualification and packaging are SimWar concerns. Keep private configurations and source bytes in authorized private storage, not public commits. Do not require a submodule, local clone, new service or canon restructuring.

## Critical Decisions and simulation time

Author-approved target lengths: 6 (Short), 12 (Standard) or 24 (Extended) Critical Decisions per game (the strategic counterpart of narrative Spot-lights). The 20-decision target is REJECTED. Select the target at scenario setup. A Critical Decision is a consequential player commitment arising from dramatic strategic tension, whose resolution can materially alter the developing situation, faction interests, relationships, obligations, capabilities or future opportunities. Deliberate inaction may qualify. Routine resource expenditure is not inherently dramatic. A simulation Turn is an interval for adjudication, not inherently a Critical Decision. Reading briefings, inspecting maps, discussing alternatives, clarifying intent, executing already committed orders, mechanical resolution and autonomous faction decisions do not independently consume the player's budget.

DONE (mechanical, PR #102): implemented optional game length and replayable Critical Decision records within the existing request ledger. Private start supports --game-length; commit-decision binds to the current session revision and records a confirmed order or deliberate abstention. Counts are derived and actor-local; ordinary requests and model decisions do not increment them. Focused tests and CI passed (45881735000, 45881734972); experiential pacing qualification remains WIP. Use stable identity and explicit significance classification; avoid duplicate counts for follow-through. Keep the fictional clock, scenario deadlines and autonomous faction decisions independent. Do not invent pressure, force a decision, or terminate the game solely because the target is reached. Validate pacing in actual play before imposing further rules. Preserve existing fixed-interval mechanical fixtures; the Fiji 12-week test is not automatically a qualified 12-Critical-Decision game.

## NEXT — lean implementation sequence

| Step | Deliverable | Exit test |
|---|---|---|
| 1 | DONE (PR #82, CI passed): optional dated organization context bound to existing actors using the participant compiler; no duplicate mutable stocks. Fiji pilot needs only its existing relief objective, aid resources and dated history. | Faction context and authority are consistent; no invented canon or individual-agent model. |
| 2 | DONE (PR #83, both CI workflows passed): native Shortfall bands and bounded weekly project progression using existing state and ledger; deterministic delay policy, no character tests. | A project can progress, stall or change scope; resource guards and replay hold. |
| 3 | DONE (PRs #85–86, CI passed): funded capacity decisions and actor-local model choice/abstention. Private adapter now wired; live model qualification pending. | Unsupported effects are rejected; independent decisions and ignored events remain consistent. |
| 4 | DONE (mechanical): preserve Fiji recovery as a regression fixture. Vault #993 and #995 (runs 45873529443, 45882376581) verified contrasting outcomes, portable source equivalence, exact replay, actor visibility and independent partner abstention. WIP (P1): qualify compelling strategic gameplay separately. | Author-led play with consequential alternatives, evolving circumstances and justified pacing; no forced decision quota. |
| 5 | PENDING (P2): Carry forward only consequential faction conditions, commitments and resources into a successor scenario; qualify reviewed scenario generation and public/private ZIP delivery. | Meaningful campaign continuity, frozen configuration, correct visibility and verified execution. |

Keep existing civic fixtures for regression. Do not build another generic campaign before the SH44SER vertical slice unless a concrete test requires it. Conflagration inventory remains partial; qualify supported civilian/institutional content only. Add bounded Sarna Len content later using native DXD. Great War and Solo City are supporting sources, not additional engines to port.

## Current implementation increment — strategic turn support

- DONE (PR #97; tests 45878260145 and bundle 45878260151 passed): actor-local derived project assessments, conditional single-investment costs and capacity effects, report-cutoff deltas, pending orders and latest project results. No new scenario properties or adjudication rules. Focused regression checks passed.
- DONE (mechanical, PR #97): revision-bound one-turn resolution with exact pending faction response map; existing packet validation and checkpoint replay reused. Chat facilitator procedure documented. Model behavior and actual player-led gameplay not yet qualified.
- DONE (mechanical): connector-backed pinned source resolver for JSON, Markdown and PNG; exact blob bytes checked; same compilation/provenance contract. PR #99 merged; connector equivalence/tamper tests passed, but shared scenario-profile regression failed both workflows (45880014941, 45880014822). Shared duration regression corrected; #102 CI and vault #995 private qualification passed. No local checkout requirement for transferred sources.
- DONE (mechanical): vault #995 exported a verified portable scenario package (artifact 15147307624, run 45882376581). Public engine and private package are independently versioned.
- NEXT (P1): select a bounded SH44SER consim designed for meaningful faction-level interactions, informed by native properties and actual gameplay needs. Author-led qualification remains pending. Retain Fiji's existing mechanics and clock for regression.
- DEFERRED: milestone-grant experiment on `feat/strategic-milestone-grants`; do not merge or extend solely to increase decision density. Reconsider only when a reviewed scenario requires it.

## COIN-informed faction interaction foundation

Author-approved design direction: factions pursue their own asymmetric goals, with alignment, neutrality or conflict arising between particular goals in context. Draw design lessons from GMT's People Power (XI), A Distant Plain (III) and Fire in the Lake (IV): distinct objectives, coupled consequences, constrained opportunities, independent actors and periodic reassessment. Do not port card decks, eligibility tracks, tactical operations, universal support ratings or non-player flowcharts.

| Priority | Status | Increment |
|---|---|---|
| P1 | DONE (mechanical) | PR #111 actor strategy tests passed; shared CI failed only on narrative forced-sleep regression (45893817282, 45893817233). Full bundle qualification pending shared fix. |
| P1 | WIP | Donor-authorized resource transfers between distinct existing civilian investment stocks; coupled domestic/recipient opportunities, FIFO review, conservation, actor-local feasibility and replay tests. No binding reciprocal agreements yet. |
| P1 | PENDING | Bounded referee-proposed developments with explicit prerequisites, authorized effect types, provenance, visibility and deterministic replay. No unrestricted model deltas. |
| P1 | PENDING | Dramatic decision presentation and downstream reassessment; qualify divergent outcomes in author-led play. |
| P2 | DEFERRED | Additional mechanics absent a demonstrated scenario requirement. |

The referee interprets goal interactions from actor-visible circumstances. Do not persist a universal alignment matrix or infer private motivations as public fact. Priority order guides qualitative judgment, not a numerical utility function. Existing objectives retain their independent observed success criteria. Factions may achieve overlapping objectives; no required zero-sum winner.

## NEXT — Fallout Period coalition consim

Selected for design review: the Shanter–Fiji–Vanuatu Coalition (2003–2006), canonically described in [Reconstruction Period Milestones](https://github.com/robert-kurcina/vault-sh44ser/blob/c918766d434453644a137cfadfa901f4a8be96b5/01_Foundations/02_History/05_Reconstruction_Period_Milestones.md), heading "Shanter-Fiji-Vanuatu Coalition". Use a bounded episode rather than simulate the entire period. The existing Fiji recovery fixtures remain regression references.

- WIP: review dated national histories, coalition organization, native economy/logistics rules and geography. Pin exact relevant sources; distinguish established roles from reviewed assumptions. Shanter, Fiji and Vanuatu are candidate player perspectives within one scenario; RWF is a candidate external institution only after its historical establishment. Do not invent pre-2003 institutions or back-project 2044 statistics.
- NEXT: draft a Short (6 Critical Decisions) playable episode with competing national and shared objectives, voluntary coordination, finite civilian resources, port/service constraints, meaningful independent faction choices and observable consequences. Choose fictional duration from the episode, not the pacing target. Prefer existing project, request, consent, event, clock and visibility mechanics; identify only concrete unsupported interactions requiring implementation. Do not add generic ratings or force six decisions.
- PENDING: review assumptions, select the minimal missing adjudication rules if needed, author private scenario configuration, test alternate outcomes and conduct actual author-led Chat play. Do not treat the canonical coalition outcome as a forced player result; mark exercise divergences as hypothetical, not canon edits.

## Gameplay qualification

A strategic turn must present a changed situation, meaningful faction-level alternatives, opportunity costs and observable consequences. Use existing actor views, conditional events and accounting before adding mechanics. At least two plausible strategies must produce materially different intermediate states and outcomes; independent factions or scheduled developments must matter even when ignored. Show commitments, bottlenecks, uncertainties and decision-relevant geography. Do not import narrative character mechanics or require SH44SER corpus expansion. Qualify one authorized recovery slice before broadening content; distinguish actual play evidence from CI.

## Repository ownership correction — 2026-11-26

- DONE: audit of vault-sh44ser SimWar PRs #977–#993 and repository boundaries. Public runner already contains generic private play, source compilation, project economy, faction decisions and regression tests; do not duplicate these.
- DONE: runner #89 migration safeguards and public CI; vault #993 scripted strategic qualification (export failed separately), #994 export correction merged.
- DONE: corrected private export and all regression/strategic/browser verification passed (vault run 45873796338, artifact 15144621110).
- WIP (P1): move generic package/qualification tooling to SimWar and establish durable authorized private versioned scenario access; preserve SH44SER as the read-only dependency. The earlier local-only migration procedure is superseded in that respect: a Mac-local copy is optional, not an architectural dependency. Decide private companion repository versus private runner before migration; neither is authorized by this plan alone.
- BLOCKED: vault cleanup until complete, byte-verified private retention and replacement execution are confirmed. Never copy private content into public commits or bundles.
- REJECTED: mandatory local-only private scenario storage for Chat-first gameplay.
