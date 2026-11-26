# Narrative game development plan

Status: WIP — 2026-11-26. Shared constraints: [master plan](PLAN.md).

## Goal and evidence

Create playable character-centered adventures with exploration, danger, uncertainty, meaningful decisions and consequences. ChatGPT presents scenes and interprets player intent; Python adjudicates and commits state. Preserve native DXD and source authority.

The author’s Boothbay trial on engine revision `41c68e1ba384a53085d087a209b01ba752d832b4` ended voluntarily at turn 11/20 after ten fictional hours. Six discoveries, two unsuccessful attempts, a precaution and recovery actions yielded little apparent branching or danger. The reported legal-action count fell from ten initially to six at turns 8–10. The simple conversation export omits menu contents, so inspect scenario and engine before attributing the behavior to a specific implementation defect. The author reports that later choices did not open new options. Execution succeeded; experiential qualification did not.

## NEXT — Boothbay vertical slice first

| Step | Deliverable | Exit evidence |
|---|---|---|
| 1 | Audit current Boothbay canonical content, actions, prerequisites, effects, clock, events, DXD tests and Chat presentation. Replay reported path where inputs/seed are available; otherwise document a representative reproduction. | Identify actual branch and consequence gaps; preserve source provenance. |
| 2 | Reuse existing predicates and state for discovery-driven opportunities, location access and context-dependent follow-ups. Support revisiting or retrying where fiction permits; remove actions only for meaningful reasons. | Important discoveries or decisions open, modify or close options; at least two materially different routes. |
| 3 | Use existing clock and conditional/scheduled events to advance threats and NPC responses. Add only necessary scenario flags or counters. | Time and interference can change the situation; a precaution affects a later event or resolution. |
| 4 | Make native DXD outcomes consequential: success, failure or partial information as supported by rules; alternative approaches, exposure, lost opportunity or changed access where warranted. | Failed attempts do not uniformly become dead ends or condition penalties; risk is legible without revealing hidden facts. |
| 5 | Improve Chat scene presentation: concrete observations, grounded dialogue, changed circumstances, concise condition deltas, notebook on request, inline icons and current choices. Offer free-form intent mapped to supported actions; clarify unsupported intent without consuming a turn. | Player can understand stakes and act without reading a repetitive execution audit; no invented state changes. |
| 6 | Qualify Boothbay via actual Chat play and a compact regression suite, then adapt Castine and Ram Island. | Distinct routes and outcomes, visible danger and consequences, exact replay of accepted inputs, author feedback. |

## Design constraints

- Do not require every clue to unlock an action. Information can change judgment, access, risk or test context. Avoid checklist depletion and artificial gating.
- Present a small number of salient choices without hiding other legal actions; allow a complete menu on request. No predetermined story sequence masquerading as agency.
- Use the existing action/event/state model first. Add mechanics only after demonstrating a gap. No universal dialogue tree, individual-agent simulation, procedural story engine or exhaustive social model.
- Threats must have understandable warning signs where fiction allows; uncertainty is not arbitrary punishment. Do not force combat or a successful ending. Departure remains a valid decision with grounded consequences.
- Narration must distinguish observation, inference and unresolved mystery. No unsupported canonical additions, fabricated outcomes or revelation of hidden engine state. Any new scenario content must be reviewed and labeled as scenario assumptions if not canonical.
- Keep engine execution and checkpoints authoritative but put routine technical attestations behind a compact status or on-request diagnostic. Preserve horizontal icon/label alignment.

## Acceptance and scope

Use a baseline reproduction and a few contrasting plays: a clue-driven route, a different investigative route, and a delay or failed-action route. Verify that their intermediate states differ, not merely ending scores. Exercise precaution and departure effects, guard hidden information, and verify deterministic replay. Do not impose arbitrary branch counts per clue or a turn quota as evidence of quality. Author play feedback is the experiential gate; automated tests cannot replace it.

After Boothbay qualification, migrate the other Fear! scenarios using the same primitives, respecting their distinct clocks. Sarna Len remains pending; add a bounded native DXD slice only after this narrative foundation is qualified. Other narrative campaigns remain deferred until needed.
