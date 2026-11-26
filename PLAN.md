# Development plan

## Product scope and delivery boundaries

The runner is a reusable script-first, multi-scenario, multi-perspective simulation component of AGE, not a library workflow product. Distinguish three deliverables: (1) the generic execution engine, (2) the public synthetic campaign used to validate supported behavior, and (3) externally maintained private campaign specifications. Private canon, scenario rosters and source material must not be published here.

Campaigns may contain multiple stages, each with multiple scenarios, different participant identities (including nations and factions), distinct starting conditions and asymmetric outcome criteria. Scenarios may be independent, parallel or linked by explicit approved continuity mappings; catalog prerequisites alone do not transfer state. Preserve scenario-specific objectives without assuming that every outcome is zero-sum. These are product requirements, not claims of existing implementation. Recover the original private campaign specification externally before claiming its roster or objectives are complete.

The public civilian fixtures are a means to verify causal consequences, persistence and interpretation; their content is not the definition of the generic campaign catalog. Keep the existing supported execution scope and deferred-work boundaries below.

## Product direction — corpus-first player experience

The intended product is corpus-grounded SH44SER campaign play, with a reusable runner underneath. Public civilian fixtures establish software correctness; do not continue adding fixture mechanics merely to increase test counts. Use real-world model knowledge as background, verified external sources where material, and canonical divergence records as authoritative setting overrides. A model's pretrained knowledge is not a verified historical database. Later-era figures must not be back-projected. Runtime outcomes belong to a session timeline, not canonical source files.

Adopt general player-experience ideas from WarGameLLM (https://wargamellm.com/): scenario discovery, perspective selection, concise opening/turn briefings, configurable information presentation, session resumption and model independence. Do not copy proprietary scenario text or infer correctness from competitor marketing. Preserve deterministic state ownership and source references. Supported executable scope remains civilian recovery, institutional coordination and retrospective historical context; no operational military targeting, escalation or casualty optimization.

## EXECUTION MODES — author-approved Chat-first delivery

1. Primary: ordinary ChatGPT Chat inside the AGE project. Retrieve pinned runner and authorized private scenario inputs, run the existing Python engine in the available execution environment, and present actor-visible briefings, decisions, resource summaries and actual rendered visuals in conversation. No always-running process assumed.
2. Alternative: ChatGPT Work for larger analysis and extended tasks, using the same engine and checkpoint contract.
3. Alternative: local CLI/browser and optional LM Studio / GPT-OSS inference. Preserve existing verified implementations; further browser features are not the primary delivery gate.
4. Deferred: hosted browser application, GitHub Pages deployment and MCP integration, only if a demonstrated requirement remains after Chat qualification.

ChatGPT interprets player intent and explains results; the verified Python engine owns state and adjudication. A model-generated state block, conversational memory, or a generated UI interaction alone is not evidence of engine execution. Keep private canonical inputs and session files access-controlled; never commit private state or artwork to the public runner. No remote service, custom plugin, local model, or additional browser framework is required for the initial Chat vertical slice.

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
- Private service restoration support merged after CI (PR #35); second private scenario execution verified in private CI. Shared human participation for civic agreement merged after CI (PR #42). Third private scenario verified in private CI. Local referee handoff is explicit, and each participant controls its own consent. No autonomous consent or remote multiplayer authorization.
- Model-independent natural-language request exchange merged after CI (PR #36), with session-bound proposals and explicit confirmation.
- Loopback OpenAI-compatible local model adapter merged after transport CI (PR #37). Actual inference on the user's host remains unverified.
- Interactive terminal gameplay merged after CI (PR #38). Includes scenario selection, perspective selection, briefings, manual actions, optional local interpretation, confirmation and autosave/resume.
- Optional LLM narrative briefings merged (PR #39). Structured observations remain authoritative; live inference unverified.
- Scenario-authored hypothetical presets merged (PR #40). Private scenario configurations verified in private CI; presets bind to base spec digest and session.
- Existing private geographic assets inventoried by reference, including all fourteen Near Melanesia artwork files; raster registration and temporal applicability remain unverified.
- Historical numerical calibration remains outstanding. Qualify civilian service capacity and units before replacing illustrative assumptions; do not equate national demographics with local service throughput.

- Private continuity merged after CI (PR #44); linked private recovery verified with standard and limited-resource configurations, persistence and completed-session reporting. Independent branches are not pooled.
- Actor-visible resource dashboard and observed-history export merged after CI (PR #45). Standalone HTML is a read-only session snapshot, not a live browser game. Optional Leaflet map export merged after CI (PR #46); private Fiji map configuration merged. Direct screenshot inspection remains outstanding. Standalone pinned PNG image mode merged after CI (PR #47); private reference gallery merged. Actor-filtered image annotations with authored hex identifiers merged after CI (PR #48). Private gallery and dashboard browser smoke checks passed after runner compatibility correction; direct screenshot review, actual private pixel control points and live tiles remain outstanding. External map services require explicit user activation.

- Post-Agreement civilian service recovery verified privately; five illustrative scenarios across four groups.
- Shared framework-independent loading UI (SVG spinner, suspense skeleton, accessible busy state, reduced-motion, timeout and retry) merged after CI (PR #49) for actual map library/artwork/tile loading. Apply the same pattern to scenario/session loads, confirmed requests and narrative generation when asynchronous gameplay UI is implemented. Do not insert artificial delays or replace already available observations.

- Local single-session browser gameplay adapter merged after CI (PR #50): existing verified session, explicit request confirmation, one-turn adjudication, autosave, revision-bound requests, loopback-only HTTP and shared loading indicator. This is a trusted local single-writer interface, not remote multiplayer or deployment. Browser transition verification and scenario selection remain outstanding; these are alternative-mode improvements, not Chat delivery prerequisites.

## NEXT (ordered, with acceptance criteria)

1. Qualify actual ordinary Chat execution: retrieve pinned engine code and a supported private scenario with authorized source access, materialize required files into the Python runtime, execute a real opening briefing and turn, and capture a verified checkpoint. If connector-to-runtime transfer is unavailable, use an explicit user-provided archive or mounted project file; never claim a connector reference alone is a runnable local file.
2. Complete an entire private scenario through Chat, including player-confirmed decisions, actual engine adjudication, observation-only narrative, visible resource history and a final outcome. Verify at least one rejected/stale request and one linked continuation using existing mechanics. Keep each increment focused on actual play rather than additional fixtures.
3. Demonstrate checkpoint export and resumption after runtime reset, then across a separate conversation. Use an explicit durable user-controlled private checkpoint (download/upload or verified project storage). Pin the runner revision and input provenance; verify saved state and revision before accepting a new turn. Do not assume memory, a sandbox path, or a chat transcript is durable storage. Reject ambiguous/stale checkpoints and avoid silently overwriting an earlier branch.
4. Present actual actor-visible map/dashboard output in Chat: reuse engine rendering and structured observations. Qualify delivery of original private artwork through authorized transfer; do not substitute invented maps or screenshots. Use a compact textual briefing and controls only when they submit actual user instructions; verify each mutation in the engine. Preserve available state during real loading; do not add fake spinners or progress.
5. Expand source-qualified private scenario coverage and recover the original roster where possible. Distinguish documented, provisional and unsupported entries. Do not invent canon or block playability on exhaustive calibration. Qualify reviewed context discovery as needed for actual scenarios.
6. After Chat acceptance, qualify optional Work and local model/browser modes according to demand. Consider MCP/hosting only if the verified Chat flow cannot meet a concrete requirement. Automated Scenario Exploration remains a late-priority independent milestone.

## CHAT GAMEPLAY CONTRACT — primary delivery acceptance

- Startup: identify the authorized campaign, scenario, perspective and preset; verify exact engine/source revisions; compile and initialize through the existing engine. Store the opening checkpoint and present actor-visible context, objectives, known reports, and permissible actions.
- Turn: translate player intent into an existing allowed request, clarify material ambiguity, obtain explicit confirmation for a proposed action, bind it to the current checkpoint revision, and execute only through the engine. Advancing time is a separate explicit operation unless the player requests both. Shared participation requires each human's own consent; do not infer agreement.
- Output: present actual engine results, observation timestamps, pending requests, remaining options, and concise clearly distinguished narrative. Do not expose hidden state, raw private corpus passages, or other perspectives in player-facing displays. Label illustrative numerical assumptions and unresolved historical calibration.
- Persistence: export a verified checkpoint with provenance and revision information on every successful mutation; retain previous checkpoint until the new one is saved. On resumption, load and verify the exact checkpoint before acting. A new conversation must be able to resume without replaying conversational prose.
- Failure: if runtime, source retrieval, verification or checkpoint persistence fails, report which step failed; do not report fictional execution or successful state changes. Offer the supported file handoff or local CLI as fallback.
- Acceptance evidence: actual ordinary Chat tool execution, real verified initial/final checkpoints, complete scenario, linked continuation, resumed checkpoint in a separate conversation, and engine-derived visual output. Public CI alone does not satisfy this end-to-end acceptance. Avoid a new API or adapter if existing CLI/functions and a concise operating contract suffice.

## SOURCE-REFERENCE ARCHITECTURE (author-approved)

See [ADR-001](docs/adr/001-canonical-source-references.md). The world-building repository remains authoritative; the runner must not manually duplicate canon. Private package references, source qualification, compilation and generated session snapshots remain separate from public fixtures.

1. Qualify the existing corpus ownership map, identifiers, temporal coverage and machine-readable data before choosing an extraction mechanism. Recover the private campaign inventory externally.
2. Define a minimal reference contract (repository identity, revision, path, stable entity/field selector, effective date, provenance classification); use an explicit allowlist of source owners. Do not require a new national database.
3. Implement a local, read-only reference resolver and compiler against synthetic fixtures first. Acceptance: deterministic compilation, explicit failures for missing or ambiguous fields, temporal mismatch, stale source detection and immutable pinned snapshots. No network or private repository dependency in public CI.
4. Extend the verified private civilian pilot with reviewed numerical inputs only when evidence is sufficient. Keep authored facts in their existing authoritative homes; store only simulation-specific assumptions in the private package. Do not claim predictive accuracy from successful compilation.

## GAMEPLAY MAP AND VISUALIZATION — shared engine-derived presentation (author-approved)

Use minimum sufficient geographic fidelity for informed gameplay. One shared lightweight Leaflet renderer; interchangeable permitted basemap tiles, SVG and GeoJSON overlays, and optional H3 geographic indexing only where useful. Existing canonical raster and hex maps remain authoritative for fictional geography; preserve their identifiers rather than replacing them with H3 cells. No mandatory ArcGIS SDK, dedicated GIS database, comprehensive GIS pipeline or terrain reconstruction.

1. Define scenario region, initial zoom, permitted basemap, source-qualified locations and applicable overlays in configuration. Inventory existing private map artwork and register it with verified control points where needed. Retain a local image-map option when geographic registration is unnecessary.
2. Export actor-visible resource balances, observed trends, objective progress and knowledge timestamps from the existing engine. Render a concise resource dashboard from actual session data.
3. Implement the shared map canvas with pan, zoom, layer toggles, geographic location selection, basic geographic distance measurement and SVG/GeoJSON annotations. Demonstrate actual browser rendering with real tiles and source attribution, not archive photographs or generated mockups.
4. Add optional simplified terrain presentation from available, appropriately dated geographic sources and canonical artwork. Use broad land-cover, relief and water classes, keep unknown terrain unknown, and distinguish modern reference imagery from historical conditions. Avoid unnecessary raster processing; terrain presentation is not a new adjudication rule.
5. Add optional H3 indexing if a supported scenario needs geographic aggregation; retain existing authored hex maps independently. Display supported civilian service locations, relationships, and resource information through actor-visible overlays. Use the same read-only contracts for eventual MCP delivery.

Acceptance: actual engine-derived scenario visuals and resource information from a private session, deliverable in Chat. Existing browser rendering remains an alternative; live tiles, selectable overlays and geographic registration are required only where a supported scenario needs them. Keep private artwork local/access-controlled and comply with tile provider attribution and use restrictions. Do not introduce operational military logistics or targeting tooling. No mandatory cloud GIS, new elevation model, bathymetric reconstruction or comprehensive digital twin.

## DEFERRED OPTIONAL — ChatGPT-native MCP plugin (previously approved; not a Chat prerequisite)

Do not begin plugin development until ordinary Chat gameplay acceptance is satisfied and a concrete requirement warrants an external service. Optional local model connectivity is not a release gate unless separately required. Keep GitHub as source control; do not migrate the engine to JavaScript or require a browser UI merely for plugin integration.

1. Verify current ChatGPT custom plugin eligibility, MCP transport and authentication requirements, and select a suitable executable hosting environment. GitHub Pages alone cannot host executable MCP functions.
2. Expose read-only campaign listing and session inspection for the existing civilian synthetic campaign through a minimal MCP adapter. Verify actual invocation from ChatGPT.
3. Expose bounded human-directed civilian session operations only after validating authorization, input contracts, session isolation, persistence and retry safety. The Python engine remains authoritative; ChatGPT interpretation is not authoritative state.
4. Verify end-to-end use, including resuming a session and exporting results. Keep private campaign material external and access-controlled; do not publish it to the public repository.
5. Consider GitHub Pages for optional documentation or reports only. No mandatory browser frontend or local installation in the remote-hosted configuration.

Acceptance: a user can operate a supported civilian campaign from ChatGPT through the deployed plugin, with the same verified engine behavior as the CLI. Hosting and account eligibility must be demonstrated, not assumed.

## LATE PRIORITY — Automated Scenario Exploration (author-approved)

After supported scenario configurations, interactive gameplay and private continuity are stable, add an optional research mode for civilian recovery and institutional coordination. This milestone must not displace current Chat gameplay qualification or source-qualified scenario coverage.

1. Establish deterministic civilian participant baselines and explicit experiment assumptions before adding model-generated behavior.
2. Explore reviewed civilian resource, service-capacity, reporting-delay and institutional cooperation variations using isolated sessions and the existing adjudication engine.
3. Add optional LLM-controlled civilian participants with separate actor-visible context, constrained existing actions, and recorded model configuration and decisions. No unrestricted state mutation or inferred consent.
4. Where justified, introduce seeded uncertainty distributions with documented assumptions; compare outcomes, sensitivity, and failure modes against deterministic baselines. Repeated model outputs are not independent empirical observations.
5. Report conditional outcome distributions, uncertainty, and limitations; retain session provenance and replay. Do not treat frequency as calibrated historical probability or automatically revise canon.

Acceptance: a reproducible civilian experiment compares reviewed scenarios and participant policies, with outcome summaries clearly distinguished from verified facts. Operational military targeting, escalation, casualty optimization and autonomous combat decision support remain outside executable scope.

## DEFERRED
- Private campaign content belongs in an external private package, not this public repository. Recover its original stage and scenario inventory, participant perspectives, chronology, objectives and continuity requirements from authorized private sources; record unknowns rather than inventing canon.
- Historical reconstruction may be represented by documented milestones and retrospective civilian consequences; no operational military escalation, targeting, or optimization of casualties.
- Hosted deployment, further standalone browser UX, autonomous actor policy, general causal inference, AGE/AIGen integration, rich UI and stochastic models are not primary delivery requirements. Reassess only after the civilian vertical slice works.

## REJECTED
- Counting repeated plans, additional isolated demonstrations or documentation-only changes as functional implementation.
- Publishing private corpus material.
- Generated prose as authoritative state or unrestricted runtime-generated rules.
- New infrastructure without a demonstrated scenario requirement.

## Execution discipline
Each development increment must complete an acceptance criterion or a concrete implementation step toward it, or explicitly document a blocker. Update this file after each increment. Review verification appropriate to the change before merging: direct review for documentation and inventory, targeted execution/regression tests for code. Do not count an unverified branch as done.

## DONE — Chat checkpoint handoff (PR #52 merged)

- Implemented a standalone, portable, revision-bound JSON session handoff in `chat_handoff.py` (export, verify and restore), including embedded scenario, deterministic checkpoint verification, session/scenario/payload digests and exclusive restore-path creation. Public fixture regression tests added in `test_chat_handoff.py`.
- Limitations: commit SHA is operator supplied and is **not cryptographically attested** to the loaded code; SHA-256 hashes are integrity checks, not authenticity signatures. Private sources and canonical artwork are not included. Cross-conversation persistence is not demonstrated until an actual handoff is uploaded and restored in a fresh Chat runtime.
- Verification: PR #52 test workflow 45760047208 succeeded on Python 3.10 and 3.12. Do not mark NEXT 1–4 as accepted on this basis.
- Next: verify public CI, qualify exact-file transfer into the Chat Python environment, execute a supported scenario using actual engine code, and demonstrate export/import plus source-qualified private continuation. Avoid further frontend work until Chat gameplay works.

## CURRENT INCREMENT — Offline Chat runtime transfer (PR pending)

- Direct Git clone in Chat's Python container failed with DNS resolution error. GitHub connector file reads and Actions remain accessible.
- Added a GitHub Actions workflow to test the pinned source, exercise a public opening/submit/advance/handoff/restore/finish/linked continuation, and export an exact tracked-source ZIP with revision and SHA-256 manifest. No private source or session is included. Artifact delivery is an explicit manual download/upload fallback; connector-to-runtime byte transfer is not assumed.
- Acceptance remains pending: successful workflow, actual archive transfer, checksum verification, execution inside Chat and separate-conversation resumption. CI execution alone does not qualify Chat.
