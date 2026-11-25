# Development plan

## DONE
- Deterministic scheduled-event runner, actor reports, checkpoints and replay.
- Administrative request ledger, review capacity, read-only interpretation exchange and completed-session comparison.
- Standalone request-dependent library service example (PR #14 merged; 37 tests passed in Python 3.10 and 3.12).
- Existing examples are regression fixtures, not the product objective.

- Campaign-oriented reset (PR #15 merged after CI).

- P0 campaign catalog: three synthetic scenario files and catalog validation (PR #16 merged; 39 tests passed on Python 3.10 and 3.12).

## WIP
- P1 playable civilian recovery vertical slice is next; no implementation claimed yet.

## NEXT (ordered, with acceptance criteria)
2. Playable civilian recovery vertical slice: integrate a narrowly scoped, human-directed public-service restoration rule with the existing runner, rather than extending the standalone example. Acceptance: two human choices lead to different service outcomes under identical initial conditions, persisted and replay-verified, with resource accounting and actor-visible reporting.
3. Scenario variety: add a humanitarian assistance scenario and a civic negotiation scenario in the public synthetic campaign. Acceptance: each has distinct objectives and completion criteria, executes using shared chronology and persistence; no duplicated runner.
4. Campaign continuity: explicitly export approved civilian recovery outcomes and import them into a later scenario. Acceptance: two completed sessions can yield distinct valid starting conditions; provenance identifies the source session and variables. Independent starts remain supported.
5. Local model commentary: optionally connect read-only summarization of the public civilian scenario to a local model; verify actual invocation before claiming completion. No model-generated state changes.
6. Campaign usability: provide a single documented workflow to list scenarios, start, inspect, submit permitted civilian requests, advance, finish and compare sessions. Acceptance: run the public campaign end to end using the documented commands.

## POST-STABILIZATION — ChatGPT-native MCP plugin (author-approved)

Do not begin plugin development until the current Python/CLI engine has satisfied its existing functional acceptance criteria, including campaign continuity and end-to-end execution. Optional local model connectivity is not a release gate unless separately required. Keep GitHub as source control; do not migrate the engine to JavaScript or require a browser UI merely for plugin integration.

1. Verify current ChatGPT custom plugin eligibility, MCP transport and authentication requirements, and select a suitable executable hosting environment. GitHub Pages alone cannot host executable MCP functions.
2. Expose read-only campaign listing and session inspection for the existing civilian synthetic campaign through a minimal MCP adapter. Verify actual invocation from ChatGPT.
3. Expose bounded human-directed civilian session operations only after validating authorization, input contracts, session isolation, persistence and retry safety. The Python engine remains authoritative; ChatGPT interpretation is not authoritative state.
4. Verify end-to-end use, including resuming a session and exporting results. Keep private campaign material external and access-controlled; do not publish it to the public repository.
5. Consider GitHub Pages for optional documentation or reports only. No mandatory browser frontend or local installation in the remote-hosted configuration.

Acceptance: a user can operate a supported civilian campaign from ChatGPT through the deployed plugin, with the same verified engine behavior as the CLI. Hosting and account eligibility must be demonstrated, not assumed.

## DEFERRED
- Private campaign content belongs in an external private package, not this public repository.
- Historical reconstruction may be represented by documented milestones and retrospective civilian consequences; no operational military escalation, targeting, or optimization of casualties.
- Autonomous actor policy, general causal inference, AGE/AIGen integration, rich UI and stochastic models are not delivered. Reassess only after the civilian vertical slice works.

## REJECTED
- Counting repeated plans, additional isolated demonstrations or documentation-only changes as functional implementation.
- Publishing private corpus material.
- Generated prose as authoritative state or unrestricted runtime-generated rules.
- New infrastructure without a demonstrated scenario requirement.

## Execution discipline
Each development increment must complete an acceptance criterion or a concrete implementation step toward it, or explicitly document a blocker. Update this file after each increment. Review CI before merging; do not count an unverified branch as done.
