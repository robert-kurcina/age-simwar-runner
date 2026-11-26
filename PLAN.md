# Development plan

## Product scope and delivery boundaries

The runner is a reusable script-first, multi-scenario, multi-perspective simulation component of AGE, not a library workflow product. Distinguish three deliverables: (1) the generic execution engine, (2) the public synthetic campaign used to validate supported behavior, and (3) externally maintained private campaign specifications. Private canon, scenario rosters and source material must not be published here.

Campaigns may contain multiple stages, each with multiple scenarios, different participant identities (including nations and factions), distinct starting conditions and asymmetric outcome criteria. Scenarios may be independent, parallel or linked by explicit approved continuity mappings; catalog prerequisites alone do not transfer state. Preserve scenario-specific objectives without assuming that every outcome is zero-sum. These are product requirements, not claims of existing implementation. Recover the original private campaign specification externally before claiming its roster or objectives are complete.

The public civilian fixtures are a means to verify causal consequences, persistence and interpretation; their content is not the definition of the generic campaign catalog. Keep the existing supported execution scope and deferred-work boundaries below.

## DONE
- Deterministic scheduled-event runner, actor reports, checkpoints and replay.
- Administrative request ledger, review capacity, read-only interpretation exchange and completed-session comparison.
- Standalone request-dependent library service example (PR #14 merged; 37 tests passed in Python 3.10 and 3.12).
- Existing examples are regression fixtures, not the product objective.

- Campaign-oriented reset (PR #15 merged after CI).

- P0 campaign catalog: three synthetic scenario files and catalog validation (PR #16 merged; 39 tests passed on Python 3.10 and 3.12).

- P1 integrated civilian restoration rule, resource accounting, actor-visible fulfillment, replay and comparison (PR #19 merged after Python 3.10/3.12 CI success).

- P2 distinct playable synthetic assistance and agreement scenarios (PR #20 merged after successful CI).

- P3 mapped campaign continuity, provenance verification and multiple-scenario stage support (PR #21 merged after successful CI).

- ADR-001 merged in PR #22 after successful CI.
- Local pinned structured source compiler (PR #23 merged after successful CI).

- Bounded civilian scenario variation overlays (PR #24 merged after successful CI).

- Unified local campaign CLI and linked end-to-end workflow (PR #25 merged after successful CI).

- Pinned Markdown evidence references (PR #26 merged after successful CI).

## WIP
- External private civilian recovery pilot configured with pinned narrative evidence and explicitly hypothetical quantities. A private verification script and scoped CI workflow have been added; execution against the actual private checkout is not yet confirmed. Historical numerical calibration remains outstanding.

## NEXT (ordered, with acceptance criteria)
5. Local model commentary: optionally connect read-only summarization of the public civilian scenario to a local model; verify actual invocation before claiming completion. No model-generated state changes.

## SOURCE-REFERENCE ARCHITECTURE (author-approved)

See [ADR-001](docs/adr/001-canonical-source-references.md). The world-building repository remains authoritative; the runner must not manually duplicate canon. Private package references, source qualification, compilation and generated session snapshots remain separate from public fixtures.

1. Qualify the existing corpus ownership map, identifiers, temporal coverage and machine-readable data before choosing an extraction mechanism. Recover the private campaign inventory externally.
2. Define a minimal reference contract (repository identity, revision, path, stable entity/field selector, effective date, provenance classification); use an explicit allowlist of source owners. Do not require a new national database.
3. Implement a local, read-only reference resolver and compiler against synthetic fixtures first. Acceptance: deterministic compilation, explicit failures for missing or ambiguous fields, temporal mismatch, stale source detection and immutable pinned snapshots. No network or private repository dependency in public CI.
4. Validate one private civilian recovery scenario with reviewed historical/canonical inputs and scenario-specific overlays. Keep authored facts in their existing authoritative homes; store only simulation-specific assumptions in the private package. Do not claim predictive accuracy from successful compilation.

## POST-STABILIZATION — ChatGPT-native MCP plugin (author-approved)

Do not begin plugin development until the current Python/CLI engine has satisfied its existing functional acceptance criteria, including campaign continuity and end-to-end execution. Optional local model connectivity is not a release gate unless separately required. Keep GitHub as source control; do not migrate the engine to JavaScript or require a browser UI merely for plugin integration.

1. Verify current ChatGPT custom plugin eligibility, MCP transport and authentication requirements, and select a suitable executable hosting environment. GitHub Pages alone cannot host executable MCP functions.
2. Expose read-only campaign listing and session inspection for the existing civilian synthetic campaign through a minimal MCP adapter. Verify actual invocation from ChatGPT.
3. Expose bounded human-directed civilian session operations only after validating authorization, input contracts, session isolation, persistence and retry safety. The Python engine remains authoritative; ChatGPT interpretation is not authoritative state.
4. Verify end-to-end use, including resuming a session and exporting results. Keep private campaign material external and access-controlled; do not publish it to the public repository.
5. Consider GitHub Pages for optional documentation or reports only. No mandatory browser frontend or local installation in the remote-hosted configuration.

Acceptance: a user can operate a supported civilian campaign from ChatGPT through the deployed plugin, with the same verified engine behavior as the CLI. Hosting and account eligibility must be demonstrated, not assumed.

## DEFERRED
- Private campaign content belongs in an external private package, not this public repository. Recover its original stage and scenario inventory, participant perspectives, chronology, objectives and continuity requirements from authorized private sources; record unknowns rather than inventing canon.
- Historical reconstruction may be represented by documented milestones and retrospective civilian consequences; no operational military escalation, targeting, or optimization of casualties.
- Autonomous actor policy, general causal inference, AGE/AIGen integration, rich UI and stochastic models are not delivered. Reassess only after the civilian vertical slice works.

## REJECTED
- Counting repeated plans, additional isolated demonstrations or documentation-only changes as functional implementation.
- Publishing private corpus material.
- Generated prose as authoritative state or unrestricted runtime-generated rules.
- New infrastructure without a demonstrated scenario requirement.

## Execution discipline
Each development increment must complete an acceptance criterion or a concrete implementation step toward it, or explicitly document a blocker. Update this file after each increment. Review CI before merging; do not count an unverified branch as done.
