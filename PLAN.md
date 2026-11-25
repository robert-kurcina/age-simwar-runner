# Development plan

## DONE — deterministic administrative prototype (PRs #1–12)
- Scenario configuration, clock, scheduled updates and milestone checks.
- Checkpoint v2 persistence, replay and read-only inspection.
- Actor objectives, filtered observations and deterministic report delays.
- Administrative request validation, persistence and bounded review.
- Repeatable library demonstration and manual CLI workflow.
- Read-only interpretation exchange and completed-session comparison.
- Python 3.10 and 3.12 CI: 35 tests and demonstration passed at PR #12.
- Metadata under 00_Meta.

## WIP
- Prototype closeout and scope documentation (PR #13).

## NEXT — functional development, in a non-military example
- Demonstrate an actual administrative outcome dependent on a human-submitted request, with an explicit rule, resource constraint and recorded consequence. Compare identical initial conditions with and without the request.
- Evaluate the resulting behavior before extending the model; preserve failed milestone checks rather than forcing outcomes.
- Evaluate optional read-only local LLM summarization, separately from state authority. Verify with a real model before claiming integration.

## DEFERRED
- AGE/AIGen integration contracts; richer observation models; migration; UI; multi-agent frameworks.
- Private scenario integration and original historical reconstruction objective are not delivered by this prototype.
- Autonomous decision-making and general causal adjudication are not implemented.

## REJECTED
- Generated prose as state authority.
- Publishing private corpus material.
- Runtime-generated rules with unrestricted state mutation.
- Infrastructure expansion without a demonstrated functional need.
