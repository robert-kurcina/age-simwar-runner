# Development plan

## DONE (merged and CI verified)
- Deterministic scenario execution, historical milestone checks, checkpoint persistence and replay.
- Actor objectives, filtered observations and report delays.
- Administrative request validation, persistence and bounded review.
- Checkpoint versioning and read-only inspection.
- Python 3.10 and 3.12 CI; 33 tests passed at PR #11.
- Metadata separation under 00_Meta.

- Consolidated repeatable library demonstration (PR #9 passed CI and merged).

- Read-only interpretation exchange (PR #10 merged after CI).

- External scenario configuration documentation and validation-only CLI (PR #11 merged after CI).

## WIP
- Manual administrative interaction workflow and read-only comparison of completed sessions.

## NEXT
- Review the limited prototype against its acceptance criteria; explicitly distinguish it from a completed simulation engine.

## DEFERRED
- AGE/AIGen integration contracts, more elaborate observation models, migration, UI and multi-agent frameworks.
- Private scenario integration, subject to separate scope review.

## REJECTED
- Generated prose as state authority.
- Publishing private corpus material.
- Runtime-generated rules with unrestricted state mutation.
- Infrastructure expansion without a demonstrated functional need.
