# Execution boundary

The runner is a prototype of session execution, not the authority for world generation or domain rules. External scenario data is pinned by hash. Domain rules and cognition may later enter through versioned adapters; neither is implemented in this increment.

Contract v1: relative integer minutes, integer state variables, scheduled additive updates, exact-value milestone checks. At a shared timestamp, updates execute in file order before checks. Failed checks are recorded, never repaired by forcing the expected value. Turn intervals are open at start and closed at end. Checkpoints replay from the pinned input to detect inconsistency. This is single-writer local persistence, not an authenticated ledger or multi-user service.

The public example concerns library reopening. No private scenario material is included.

Run: python runner.py scenarios/demo.json checkpoint.json --turns 2
Test: python -m unittest -v

Limitations: scheduled events only, no causal model, no hidden state or autonomous actor decisions, no stochastic resolution, no LLM. Checkpoint replay is linear in elapsed turns; acceptable for this prototype. A domain-specific adapter must not be confused with a validated real-world predictive model.

Optional `actors` maps IDs to labels and independent descriptive objectives. Each objective references an existing numeric state variable, an integer threshold, a description, and a comparison (`at_least`, `at_most`, `equal`). Evaluation is read-only, derived at initialization and turn boundaries, and never feeds back into event scheduling. This is objective reporting, not an actor policy or decision optimizer. Existing v1 scenario files remain readable; old checkpoints require recreation because their derived actor field differs.

Actor observations are explicit allowlist projections of current values and only those own objectives whose referenced variable is visible. Missing allowlist means no visible values. They exclude the full event ledger, constraint checks and other actors. CLI --actor prints this projection; the checkpoint and scenario files remain referee-only. This is logical separation, not filesystem access control or simulated intelligence acquisition. Actor observations have no effect on world state. Private state must not be supplied to an actor-facing model.

Administrative request contract: the optional action_catalog declares named requests with a description and permitted actor IDs. A trusted caller supplies the actor identity separately from the proposed action. The validator rejects unknown actions, actor overrides and extra fields; the observation view includes only the actor's permitted requests. Registration returns a detached timestamped record and does not mutate or execute simulation state. Durable request queues and domain-specific execution are outside this increment. No real-world military decision or targeting model is implemented.
