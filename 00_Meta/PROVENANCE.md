# Development provenance

## Foundation increment

ChatGPT-assisted implementation of a script-first scheduled-event runner, with author-approved experimental development and PR workflow. The public example is synthetic and non-military. The initial implementation was informed by an architectural review of the AGE session boundary; no private source text or scenario data is included.

Five unit tests were authored; execution has not yet been verified. The runner is a prototype, not a validated simulation model.

Record subsequent material design decisions, source provenance suitable for public disclosure, and verification status here or in dedicated files under this directory. Do not store private conversation transcripts or credentials.

## Increment 2

Foundation PR merged by owner. Added descriptive actor objective reporting and CI configuration; no autonomous decision policy. Local checkout was blocked by DNS/network access. CI execution must be verified before merge. Checkpoint schema change intentionally requires recreation of old prototype saves.

## Increment 3

PR #2 merged; both Python matrix jobs passed. Added default-deny actor observation projection and tests, without introducing autonomous decision-making. Observation views do not establish access control over files. No private data included.

## Increment 4

PR #3 passed both Python CI jobs and was merged by the integration using a pinned head SHA. Introduced a generic administrative request validation contract with no action effects or autonomous policies. Added five unit tests. Private scenarios remain external. CI verification of this increment is pending.

## Increment 5

PR #4 merged by the integration after both CI jobs passed. Added a durable administrative request ledger, replay checks, CLI submission and actor-owned request projections. Records do not execute actions or modify scenario values. Three tests added; CI verification pending. Old prototype checkpoints require recreation.

## Increment 6

PR #5 passed both Python CI jobs and was merged by the integration. Added deterministic historical observation projections and three regression tests, including objective side-channel prevention. No private data or military decision model included. CI pending.

## Increment 7

PR #6 passed both Python CI jobs and was merged by the integration. Added explicit checkpoint format version, scenario identity diagnostics, read-only inspection and a documented demonstration. Two tests added. Unversioned prototype saves require recreation; no migration is claimed. CI pending.
