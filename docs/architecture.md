# Execution boundary

## Current implementation

The runner is a deterministic session execution prototype, not a validated predictive model. The public example is synthetic library reopening. No private corpus material is included.

- Scenario contract v1: relative integer minutes, integer state variables, scheduled additive updates and exact-value milestone checks. At a shared timestamp, updates execute in file order before checks. Failed checks are recorded, never forced to pass.
- Turn intervals are open at the start and closed at the end. Checkpoint format v2 pins the scenario by digest and replays submitted requests and scheduled events to detect inconsistency. Unsupported checkpoint versions and changed scenario revisions are rejected.
- Actor objectives are descriptive threshold comparisons, evaluated against actual state for the referee and reported values for the actor. Visibility defaults to none. Report delays reconstruct historical values; observations before minute zero are unknown. Delayed reports are not necessarily inaccurate.
- Administrative requests are actor-bound, validated, persisted and reviewed in submission order within a configured per-turn capacity. Review records a disposition, not fulfillment. Review-only requests do not change scenario values. The opt-in civilian restoration rule spends one credit and opens one center per fulfilled request, records both effects in the ledger, and runs after scheduled updates but before same-boundary checks. The assistance and agreement fixtures share the same review, ledger and replay path: finite aid packages and independently submitted council consent. Actor projections omit global sequence numbers.
- The interpretation exchange is limited to the bundled synthetic library scenario. It exports actor-local reports and validates separately generated summary structure and packet identity, not factual accuracy. Commentary never enters adjudication.
- Read-only inspection and comparison verify checkpoints before reporting. Comparison requires completed sessions of the same scenario revision. Differences are descriptive, not causal claims.

## Limits

The CLI is a trusted referee process, not an authenticated multi-user service. Actor projections are logical information separation, not filesystem access control. Checkpoint replay is a consistency check, not proof of authorship. The implementation lacks autonomous actor decisions, general action-dependent world-variable changes beyond the three synthetic civilian rules, general causal adjudication, stochastic resolution, live model invocation and historical reconstruction.

See [scenario format](scenario-format.md) for configuration and [plan](../PLAN.md) for outstanding work. Do not equate prototype acceptance with completion of the original simulation objective.

Run: python demo.py

Test: python -m unittest -v

## Campaign continuity

A catalog entry may declare carry_from with a prerequisite scenario ID and a variables map (destination initial key to source final key). The referee explicitly exports a completed replay-verified source into a derived destination scenario and a digest-bound transition record. Verification recomputes the record from the source artifacts and current catalog. Source rules must match the source template, with initial changes allowed only for declared incoming mappings. Derived scenarios are independently executable and pinned by the existing checkpoint digest. This is consistency verification, not signature-based authentication or recursive lineage verification. Independent starts remain unchanged.
