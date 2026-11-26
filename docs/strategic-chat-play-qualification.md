# Strategic Chat play qualification — facilitator run card

This is a **play procedure**, not an additional engine or a fictional SH44SER source. Use it to run a bounded player-led strategic session with the current executable runtime and record reproducible evidence. Follow [PLAN_STRATEGIC.md](../PLAN_STRATEGIC.md) for scope and qualification state.

## Entry checks

1. Use a pinned `age-simwar-runner` main-branch revision and an authorized, pinned scenario package. Run `python game.py list` and `python game.py describe <campaign> <scenario>`; present only scenarios actually listed as executable. Private SH44SER package selection requires authorized access. Do not silently fall back to invented canon or a public civic fixture and call it SH44SER.
2. Run scenario validation and create the initial checkpoint with the existing Python entry points. Retain the exact scenario digest, engine revision, scenario source revision, seed (if configured) and checkpoint. Do not use an LLM summary as game state.
3. Identify the player's faction, its observable objectives, time horizon and 6/12/24 Critical Decision pacing target when specified. A target is advisory; simulation Turns and conversation exchanges do not consume decisions automatically.
4. Give the player only their actor-local observation. Keep referee checkpoint and other factions' unseen interests private. A report delay, missing key or unknown circumstance must remain unknown.

## One playable strategic exchange

1. **Situation.** State the current Turn/date, changed observable circumstances, faction goals, known commitments, capacities or bottlenecks and outstanding deadlines. Differentiate observed facts from LLM inferences.
2. **Tension.** Present two or more materially different *legal* courses of action, including a plausible refusal/delay when appropriate. Explain opportunity costs and what is uncertain; avoid fabricated odds or outcomes. If no consequential choice exists, advance the existing scenario clock and report what changed rather than inventing pressure.
3. **Commitment.** Ask for the player's intent and confirmation only when necessary to identify a supported operation. Use `commit_decision` with a unique stable decision ID, revision-bound command and legal action for a genuinely consequential commitment; routine inspections, negotiations and follow-through do not count as new Critical Decisions. The model chooses the interpretation; scripts decide validity.
4. **Other factions.** For configured model factions, use their actor-local `faction_packet` and record a legal choice or abstention through `accept_faction_choice`. Do not show the player's hidden state to them, or infer their private plans from referee state.
5. **Resolution.** Execute the supported engine operation(s) and `advance` only when required. Reject invalid or stale proposals; do not narrate an unexecuted effect as real. Re-open the player's `observe` projection and show the actual outcome, changed reports, unanswered questions and the next choice.
6. **Evidence.** Preserve the checkpoint and ordered inputs for `verify_checkpoint`; distinguish an accepted legal request from a fulfilled effect, observed information from current referee truth, and canonical history from hypothetical play divergence.

## Qualification matrix

Run the **same pinned scenario** through at least two plausible player strategies with the same frozen setup and independent factions. An abstention or delayed commitment should be one candidate when legal. Preserve:
- initial and final scenario/checkpoint hashes, source and engine revisions, and ordered decision IDs;
- at least one intermediate actor-local observation per path, plus an actual changed condition, project, agreement or resource where available;
- the opportunity cost and causal explanation grounded in recorded request/effect ledgers, not imagined prose;
- the independent factions' actual recorded choices, their visibility boundaries, and events that matter even when the player does nothing;
- exact replay verdict for each path and a comparison of materially different intermediate states or conclusions;
- player feedback on whether choices were understandable, consequential, surprising and worth revisiting.

A successful CI run or mechanical branch comparison is **not** experiential acceptance. If the candidate scenario cannot produce consequential alternatives without new rules, document the specific gameplay blockage before changing the shared engine. Keep the Fallout coalition setting historically bounded; any pre-2003 institution or 2044 national statistic used in a 2003 episode requires direct dated evidence or explicit scenario-review assumption.

## Stop conditions

Stop and record BLOCKED (rather than improvise mechanics) if the required authorized scenario is unavailable, the engine fails verification, a rule necessary to resolve the player's action does not exist, hidden data would have to be exposed, or source revisions cannot be frozen. Preserve the last valid checkpoint. Narrative scenario qualification follows its own plan.
