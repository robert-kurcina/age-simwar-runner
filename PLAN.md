# Development plan

## Product scope and delivery boundaries

The runner is a reusable script-first, multi-scenario, multi-perspective simulation component of AGE, not a library workflow product. Distinguish three deliverables: (1) the generic execution engine, (2) the public synthetic campaign used to validate supported behavior, and (3) externally maintained private campaign specifications. Private canon, scenario rosters and source material must not be published here.

Campaigns may contain multiple stages, each with multiple scenarios, different participant identities (including nations and factions), distinct starting conditions and asymmetric outcome criteria. Scenarios may be independent, parallel or linked by explicit approved continuity mappings; catalog prerequisites alone do not transfer state. Preserve scenario-specific objectives without assuming that every outcome is zero-sum. These are product requirements, not claims of existing implementation. Recover the original private campaign specification externally before claiming its roster or objectives are complete.

The public civilian fixtures are a means to verify causal consequences, persistence and interpretation; their content is not the definition of the generic campaign catalog. Keep the existing supported execution scope and deferred-work boundaries below.

## Product direction — corpus-first player experience

The intended product is corpus-grounded SH44SER campaign play, with a reusable runner underneath. Public civilian fixtures establish software correctness; do not continue adding fixture mechanics merely to increase test counts. Use real-world model knowledge as background, verified external sources where material, and canonical divergence records as authoritative setting overrides. A model's pretrained knowledge is not a verified historical database. Later-era figures must not be back-projected. Runtime outcomes belong to a session timeline, not canonical source files.

Adopt general player-experience ideas from WarGameLLM (https://wargamellm.com/): scenario discovery, perspective selection, concise opening/turn briefings, configurable information presentation, session resumption and model independence. Do not copy proprietary scenario text or infer correctness from competitor marketing. Preserve deterministic state ownership and source references. Supported executable scope remains civilian recovery, institutional coordination and retrospective historical context; no operational military targeting, escalation or casualty optimization.

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

- External private civilian recovery pilot compiled and replayed successfully in private CI against the pinned source and runner revisions. Narrative references resolved; illustrative resource accounting and objectives verified.

- Configurable finite civilian assistance demand and per-package yield (PR #29 merged after successful CI). Existing scenarios retain their original behavior.

- External private recovery pilot finite-demand deployment and four supply sensitivity cases verified by private CI. Hypothetical parameters remain uncalibrated.

## WIP
- Private campaign inventory merged after direct source-reference review; stage discovery metadata established, original scenario roster still incomplete.
- Private launcher and actor-visible briefing packets merged after successful CI; actual private launcher integration verified.
- Reviewed perspective-specific context binding merged and actual private briefing verified (PR #34 and private integration). Index metadata discovery utility merged; actual index query remains unverified.
- Private service restoration support merged after CI (PR #35); second private scenario execution verified in private CI. Shared human participation for civic agreement implemented in private launcher; targeted CI pending. Local referee handoff is explicit, and each participant controls its own consent. No autonomous consent or remote multiplayer authorization.
- Model-independent natural-language request exchange merged after CI (PR #36), with session-bound proposals and explicit confirmation.
- Loopback OpenAI-compatible local model adapter merged after transport CI (PR #37). Actual inference on the user's host remains unverified.
- Interactive terminal gameplay merged after CI (PR #38). Includes scenario selection, perspective selection, briefings, manual actions, optional local interpretation, confirmation and autosave/resume.
- Optional LLM narrative briefings merged (PR #39). Structured observations remain authoritative; live inference unverified.
- Scenario-authored hypothetical presets merged (PR #40). Private scenario configurations verified in private CI; presets bind to base spec digest and session.
- Existing private geographic assets inventoried by reference; raster registration and temporal applicability remain unverified.
- Historical numerical calibration remains outstanding. Qualify civilian service capacity and units before replacing illustrative assumptions; do not equate national demographics with local service throughput.

## NEXT (ordered, with acceptance criteria)

1. Recover the original private campaign inventory from authorized sources; record stage/scenario identities, chronology, perspective labels and provenance without inventing missing entries. Keep unsupported scenarios catalog-only. Acceptance: private catalog distinguishes documented, provisional and unsupported entries; no private content in public repo.
2. Deliver a private-compatible player setup and session launcher for supported civilian scenarios: select scenario and perspective, inspect opening briefing, resume pinned state, list permitted requests, submit and advance. Reuse compiler and runner; avoid a second engine. Acceptance: one private source-referenced scenario operates through the same interface as the public fixture.
3. Add model-independent read-only briefing packets from actor-visible observations and approved source context. Include date, objectives, known/unknown conditions and available civilian requests. Separate private referee material from player context. Acceptance: no hidden-state leakage and no model output accepted as state.
4. Offer natural-language civilian request interpretation as a proposal mapped to an existing action ID, requiring explicit player confirmation. Unknown or ambiguous requests fail safely. Acceptance: demonstrated local model invocation if available, with deterministic manual fallback.
5. Add named information-presentation presets and reviewed civilian scenario variants; pin configuration per session. Difficulty and realism labels must describe actual implemented differences, not cosmetic toggles or accuracy claims. Acceptance: compare documented variants without changing base canon.
6. Demonstrate complete private campaign workflow for supported scenarios, including resumption, reporting and authorized continuity. Do not block playable UX on exhaustive historical calibration; label uncertainty explicitly.
7. Reassess MCP delivery after the local workflow is demonstrated; preserve the existing authorization and hosting requirements.

## SOURCE-REFERENCE ARCHITECTURE (author-approved)

See [ADR-001](docs/adr/001-canonical-source-references.md). The world-building repository remains authoritative; the runner must not manually duplicate canon. Private package references, source qualification, compilation and generated session snapshots remain separate from public fixtures.

1. Qualify the existing corpus ownership map, identifiers, temporal coverage and machine-readable data before choosing an extraction mechanism. Recover the private campaign inventory externally.
2. Define a minimal reference contract (repository identity, revision, path, stable entity/field selector, effective date, provenance classification); use an explicit allowlist of source owners. Do not require a new national database.
3. Implement a local, read-only reference resolver and compiler against synthetic fixtures first. Acceptance: deterministic compilation, explicit failures for missing or ambiguous fields, temporal mismatch, stale source detection and immutable pinned snapshots. No network or private repository dependency in public CI.
4. Extend the verified private civilian pilot with reviewed numerical inputs only when evidence is sufficient. Keep authored facts in their existing authoritative homes; store only simulation-specific assumptions in the private package. Do not claim predictive accuracy from successful compilation.

## VISUAL DECISION SUPPORT — after private continuity, before MCP

Use existing private canonical map artwork and geographic records for sufficient gameplay-scale visualization; do not reconstruct comprehensive GIS terrain or duplicate the corpus. ArcGIS is an optional basemap/authoring provider, not a required runtime dependency. Retain interoperability with local GIS and open geographic formats.

1. Inventory source-owned artwork, map scale, local feature namespaces and reference anchors. Establish image control points, orientation, extent, datum and registration quality before claiming georeferenced imagery.
2. Export perspective-filtered resource balances and historical observed values from the authoritative existing engine. Preserve unknown/stale status and observation cutoff; do not reveal hidden state, future observations or referee-only records.
3. Render existing island imagery and optional hex overlays over a verified geographic basemap. Keep historical applicability and actor knowledge separate. Do not assume modern basemaps or later-era canonical artwork represent earlier dates.
4. Associate modeled civilian services and resource information with source-qualified locations; add civilian service dependency diagrams and institutional relationships only where supported by actual modeled data.
5. Provide consistent read-only visualization contracts for the interactive player experience and eventual MCP delivery; use deterministic rendering rather than generated illustrative imagery for authoritative views. Do not publish private assets or require hosted GIS upload.

Acceptance: demonstrate a source-linked island overlay with verified registration and a resource visualization driven by an actual private session, clearly distinguishing canonical geography, hypothetical configuration and observed simulation state. No new elevation model, bathymetric reconstruction, comprehensive geographic digital twin or operational military logistics tooling.

## POST-STABILIZATION — ChatGPT-native MCP plugin (author-approved)

Do not begin plugin development until the current Python/CLI engine has satisfied its existing functional acceptance criteria, including campaign continuity and end-to-end execution. Optional local model connectivity is not a release gate unless separately required. Keep GitHub as source control; do not migrate the engine to JavaScript or require a browser UI merely for plugin integration.

1. Verify current ChatGPT custom plugin eligibility, MCP transport and authentication requirements, and select a suitable executable hosting environment. GitHub Pages alone cannot host executable MCP functions.
2. Expose read-only campaign listing and session inspection for the existing civilian synthetic campaign through a minimal MCP adapter. Verify actual invocation from ChatGPT.
3. Expose bounded human-directed civilian session operations only after validating authorization, input contracts, session isolation, persistence and retry safety. The Python engine remains authoritative; ChatGPT interpretation is not authoritative state.
4. Verify end-to-end use, including resuming a session and exporting results. Keep private campaign material external and access-controlled; do not publish it to the public repository.
5. Consider GitHub Pages for optional documentation or reports only. No mandatory browser frontend or local installation in the remote-hosted configuration.

Acceptance: a user can operate a supported civilian campaign from ChatGPT through the deployed plugin, with the same verified engine behavior as the CLI. Hosting and account eligibility must be demonstrated, not assumed.

## LATE PRIORITY — Automated Scenario Exploration (author-approved)

After supported scenario configurations, interactive gameplay and private continuity are stable, add an optional research mode for civilian recovery and institutional coordination. This milestone must not displace current player-facing work or block MCP delivery.

1. Establish deterministic civilian participant baselines and explicit experiment assumptions before adding model-generated behavior.
2. Explore reviewed civilian resource, service-capacity, reporting-delay and institutional cooperation variations using isolated sessions and the existing adjudication engine.
3. Add optional LLM-controlled civilian participants with separate actor-visible context, constrained existing actions, and recorded model configuration and decisions. No unrestricted state mutation or inferred consent.
4. Where justified, introduce seeded uncertainty distributions with documented assumptions; compare outcomes, sensitivity, and failure modes against deterministic baselines. Repeated model outputs are not independent empirical observations.
5. Report conditional outcome distributions, uncertainty, and limitations; retain session provenance and replay. Do not treat frequency as calibrated historical probability or automatically revise canon.

Acceptance: a reproducible civilian experiment compares reviewed scenarios and participant policies, with outcome summaries clearly distinguished from verified facts. Operational military targeting, escalation, casualty optimization and autonomous combat decision support remain outside executable scope.

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
Each development increment must complete an acceptance criterion or a concrete implementation step toward it, or explicitly document a blocker. Update this file after each increment. Review verification appropriate to the change before merging: direct review for documentation and inventory, targeted execution/regression tests for code. Do not count an unverified branch as done.
