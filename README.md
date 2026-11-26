# AGE SimWar Runner

A prompt-driven scenario simulation component of AGE. Play within a single ordinary ChatGPT conversation using either the active GitHub Connector or a standalone ZIP archive and the same authoritative Python runner (Python 3.10+, standard library only).

## Quick start — play in ChatGPT

Choose either **GitHub-connected play** (live authorized source retrieval) or **standalone ZIP play** (bundled engine and campaigns, no GitHub connection needed).

### Option A — Standalone ZIP (no GitHub Connector required)

Download the `chat-runtime-<commit>` artifact from a successful main-branch [Chat runtime bundle workflow](https://github.com/robert-kurcina/age-simwar-runner/actions/workflows/chat-runtime-bundle.yml). Upload the entire downloaded ZIP into a ChatGPT conversation that supports file uploads and Python execution. Enter:

```text
Start AGE SimWar Runner from the attached ZIP. Follow START_HERE.md,
execute the bundled Python engine, and show me the available campaigns,
scenarios and participant perspectives. Keep gameplay in this conversation.
Do not connect to GitHub or reconstruct the engine in prose.
```

The artifact includes a launch guide, exact pinned source archive, revision and SHA-256 checksum. Use the [standalone launch instructions](docs/standalone-chat.md), which supersede GitHub retrieval requirements. Public artifacts contain only public campaign data. GitHub access may be needed to download an artifact initially; no GitHub account or connection is needed to play an already obtained ZIP. Artifacts expire according to the workflow retention policy. The ZIP cannot supply missing private scenarios or canonical source material; authorized private distributions are separate.

### Option B — GitHub-connected play

#### Prerequisites

- Your ChatGPT account has the GitHub Connector configured and active, with access to `robert-kurcina/age-simwar-runner`.
- The current conversation can invoke that connector and execute Python code.
- For private campaigns, your connected account also has access to the relevant private campaign and canonical source repositories. Public fixtures require no private access.

No local installation, hosted game server, MCP service, or manual checkpoint transfer is required for the intended single-conversation experience. Connector capabilities may vary by conversation; repository read access alone does not establish runtime execution capability.

#### Launch prompt

Open a ChatGPT conversation (preferably in your AGE project), activate the GitHub Connector, and paste:

```text
Using my active GitHub Connector, retrieve robert-kurcina/age-simwar-runner
and follow the ChatGPT gameplay instructions in its README.md.

Use the authoritative Python runner in this conversation's execution
environment. Discover available authorized campaigns, including associated
private campaign specifications when accessible. Present their scenarios,
participant perspectives and available presets. Let me select what to play,
then initialize the selected scenario and present its opening briefing,
objectives, known resources, relevant maps and permissible actions.

Adjudicate all gameplay through the actual pinned Python engine. Keep
the active session and verified checkpoints within this conversation.
Interpret my natural-language orders, execute confirmed actions, and
present actor-visible results and next decisions. Do not reconstruct
simulation rules or invent engine results if execution is unavailable.
```

For a quick public demonstration, add: "Start the public Civic Recovery campaign, Service Restoration scenario, as the coordinator."

### How to play

After initialization, use ordinary prompts in the same conversation. For example:

- "Show my objectives, resources and available actions."
- "Allocate one restoration credit to restore a service center."
- "Confirm that action and advance one turn."
- "Show the resource history and current map, if available."
- "Continue to the next linked scenario."

These example orders apply only when the selected scenario supports them. ChatGPT should present available choices from that scenario, not assume that all scenarios share the same actions. Explicit confirmation of a specific action is sufficient; advance time only when requested. The session remains within this thread; downloading or uploading checkpoint files is optional.

### Instructions for the ChatGPT game facilitator

1. Use the active GitHub Connector to read the repository and identify an exact engine commit. Locate the successful **Chat runtime bundle** Actions artifact for that revision (prefer a main-branch run), download it through the connector into the execution environment, verify the inner archive checksum and recorded revision, and extract it into a fresh directory. Do not assume a connector file reference is already an executable local file. A PR synthetic merge revision is acceptable only when explicitly identified and used consistently.
2. Discover campaign manifests and authorized private package references using the connector. Read required source and configuration files at pinned revisions. Transfer actual required files into the runtime; preserve source provenance. Never publish private inputs or session artifacts. Present only discovered, supported scenarios; identify unavailable content rather than inventing it.
3. Initialize through the existing `play.py` or `play.py private` entry points as appropriate. Inspect the selected actor's observation and retain a verified opening session. The Python engine owns state; ChatGPT is the player interface and interpreter.
4. For each turn, read and verify the active session, bind the intended action to its current revision, check permissible actions, and execute only confirmed requests. Use a fresh output checkpoint or preserve the previous checkpoint before mutation. Advance only as explicitly requested; shared participants control their own consent. Derive the displayed result from actual engine output. Keep narrative distinct from adjudication and never expose hidden actor information in player-facing reports.
5. Continue linked scenarios through the existing continuity functions, not by manually copying values. Present engine-derived dashboards and authorized map artwork when available; label illustrative assumptions and unknowns. Keep the game moving without requiring manual file management.
6. If actual source transfer, revision checks, Python execution or checkpoint verification fails, report the specific blocker and do not adjudicate. If the runtime resets within the thread, attempt to restore from the verified files available in that thread; if unavailable, offer a fresh start or optional file handoff. Do not simulate the engine in prose or substitute reimplemented logic. Cross-thread resumption is not a requirement.

**Current status:** The public runtime archive was successfully transferred into ordinary Chat and the pinned Python engine passed 68 regression tests there. The public opening and subsequent gameplay were demonstrated; the full private campaign prompt-to-play workflow remains to be qualified. Supported executable scope is civilian recovery and institutional coordination, not operational combat adjudication or predictive historical simulation. See [PLAN.md](PLAN.md).

## Developer and local operation reference

The remaining sections describe alternative CLI workflows and regression fixtures. They are not prerequisites for ordinary Chat gameplay.

## Campaign catalog

List or validate a local campaign without starting a session:

```sh
python campaign.py campaigns/civic-recovery/campaign.json
python campaign.py campaigns/civic-recovery/campaign.json --validate
python runner.py campaigns/civic-recovery/service-restoration.json service.json --turns 2
```

A version-1 manifest has id, title and groups. Each group has id, title and
scenarios. Each scenario entry has id (matching the referenced scenario),
title, scope, file (relative to the manifest directory) and optional
prerequisites (scenario IDs). IDs are unique within their respective
campaign namespaces. Missing references and cycles are rejected.
Prerequisites express suggested continuity, not enforced locks. Optional carry_from mappings explicitly transfer approved values when requested by the referee.
Three of the four campaign scenarios have bounded human-directed choices: restoration credits, assistance packages, and independent council consent.

## Playable civilian restoration

Use fresh checkpoint paths to compare identical starts:

```sh
python runner.py campaigns/civic-recovery/service-restoration.json baseline.json --turns 2
python runner.py campaigns/civic-recovery/service-restoration.json chosen.json --actor coordinator --request restore_service_center --turns 2
python comparison.py campaigns/civic-recovery/service-restoration.json baseline.json chosen.json
```

The baseline opens two centers; one reviewed restoration request opens a third and spends one credit. These are illustrative quantities, not empirical estimates.

## Assistance and agreement

```sh
python runner.py campaigns/civic-recovery/community-assistance.json aid.json --actor coordinator --request deliver_aid --turns 2
python runner.py campaigns/civic-recovery/civic-agreement.json agreement.json --actor council_a --request join_council_a --turns 1
python runner.py campaigns/civic-recovery/civic-agreement.json agreement.json --actor council_b --request join_council_b --turns 1
```

Each council controls its own consent. Duplicate consent does not add another participant. The fixture does not model autonomous negotiation.

## Campaign continuity

After completing the restoration session above, run:

```sh
python continuity.py campaigns/civic-recovery/campaign.json campaigns/civic-recovery/service-restoration.json chosen.json community-assistance transition.json derived-aid.json
python runner.py derived-aid.json aid-linked.json --actor coordinator --request deliver_aid --turns 2
```

The transition record pins the source checkpoint and scenario, catalog, destination template, copied variables and derived scenario. The derived scenario uses the ordinary runner; the original template remains an independent start. Transferred values are contextual observations, not causal modifiers. Preserve the source files for verification. The trusted referee is responsible for provenance and session authorization.

## Demonstration

Run `python demo.py` for a repeatable referee-side report using temporary checkpoints. The manual workflow below permits individual actor requests and inspection.

Run from the repository root using a fresh checkpoint path:

```sh
python runner.py scenarios/demo.json checkpoint.json --turns 0
python runner.py scenarios/demo.json checkpoint.json --actor library --request request_room_inspection --turns 0
python runner.py scenarios/demo.json checkpoint.json --turns 1
python runner.py scenarios/demo.json checkpoint.json --inspect --actor library
python runner.py scenarios/demo.json checkpoint.json --inspect --actor maintenance
python runner.py scenarios/demo.json checkpoint.json --turns 1
```

The library sees delayed availability reports while maintenance sees current values. Requests are recorded and reviewed in submission order, subject to administrative review capacity. Review is a disposition, not fulfillment of the requested work. The referee owns the checkpoint; actor output is a logical projection, not access control. Use a fresh path for another run. Unsupported checkpoint versions and changed scenarios are rejected.

## Optional interpretation

For the bundled public library scenario only, export a read-only interpretation prompt from an existing checkpoint:

```sh
python interpretation.py checkpoint.json --actor library
python interpretation.py checkpoint.json --actor library --response interpretation-response.json
```

The first command emits a prompt with a packet ID. A separately operated language model may return JSON containing that packet ID and a short summary. The second command validates the response structure and packet binding, but does not verify factual accuracy. The summary remains non-authoritative commentary. No provider connection, action recommendation, automatic submission or state mutation is implemented.

## External scenarios

See [scenario configuration](docs/scenario-format.md). Use `python runner.py path/to/scenario.json --validate` before starting a local session. The supported contract is scheduled events, administrative review and three opt-in synthetic civilian rules.

## Compare completed sessions

The existing CLI supports manual interaction through request submission, actor inspection and turn advancement. Use separate fresh checkpoint paths for independent sessions:

```sh
python runner.py scenarios/demo.json baseline.json --turns 2
python runner.py scenarios/demo.json alternative.json --actor library --request request_room_inspection --turns 0
python runner.py scenarios/demo.json alternative.json --turns 2
python comparison.py scenarios/demo.json baseline.json alternative.json
```

The comparison is read-only and requires completed checkpoints from the same scenario revision. It reports actual state, milestone results, objective status and administrative request counts. Differences are descriptive, not evidence of causation.

## Request-dependent service example

Run `python library_service.py` to compare two identical synthetic library
service-desk setups with and without inspection requests. Two closed study
rooms and one inspection slot per shift are assumed; a successful inspection
releases the requested room. This is a separate, deliberately domain-specific
example, not a general runner action effect or a historical model.

Use `python library_service.py --room 1 --room 2` for a custom request sequence.

## Verification

`python -m unittest -v`

See [architecture](docs/architecture.md) and [plan](PLAN.md). Public synthetic scenarios only; private scenario packages stay external.

Development provenance and LLM guidance: [00_Meta](00_Meta/).

## Pinned source compilation

See [source compiler](docs/source-compiler.md). A trusted local operator can resolve reviewed structured initial-state values from allowlisted Git repositories and produce a standalone scenario plus provenance snapshot. Existing runner and checkpoint formats are unchanged.

## Unified campaign workflow

Use `play.py` for trusted local operation of the bundled civilian campaign. Each session bundle includes a pinned scenario, checkpoint and optional incoming transition. No separate transition export is needed for this workflow. Run from the repository root using fresh session paths:

```sh
python play.py list campaigns/civic-recovery/campaign.json
python play.py start campaigns/civic-recovery/campaign.json service-restoration service-session.json
python play.py inspect service-session.json --actor coordinator
python play.py submit service-session.json restore_service_center --actor coordinator
python play.py advance service-session.json --actor coordinator
python play.py finish service-session.json
python play.py report service-session.json
python play.py start campaigns/civic-recovery/campaign.json community-assistance aid-session.json --from-session service-session.json
python play.py submit aid-session.json deliver_aid --actor coordinator
python play.py finish aid-session.json
python play.py start campaigns/civic-recovery/campaign.json civic-agreement agreement-session.json --from-session aid-session.json
python play.py submit agreement-session.json join_council_a --actor council_a
python play.py advance agreement-session.json
python play.py submit agreement-session.json join_council_b --actor council_b
python play.py finish agreement-session.json
python play.py report agreement-session.json
python play.py start campaigns/civic-recovery/campaign.json service-restoration baseline-session.json
python play.py finish baseline-session.json
python play.py compare baseline-session.json service-session.json
```

Use inspect for read-only resumption; submit records a request without advancing. Finish advances the remaining scheduled turns without additional requests. Actor projection is not an authorization boundary: the local referee owns all session bundles. Concurrent writers are unsupported. Retain previous session bundles and catalog revisions for complete transition re-verification; embedded transition checks alone do not prove recursive lineage. This CLI is limited to the four supported civilian fixture identities; compiler variations remain standalone and are not integrated into campaign continuity.

## Optional checkpoint handoff (trusted referee)

A verified local session can be exported as a portable, self-contained JSON handoff. Use the exact 40-character commit SHA of the engine checkout, not a branch name. Treat this as a provenance assertion from the trusted operator, not an independently attested engine binary. The session's scenario is embedded; the source catalog digest is retained. Keep private handoffs private.

```sh
python chat_handoff.py export service-session.json service-handoff.json --engine-revision <40-character-commit-SHA>
python chat_handoff.py verify service-handoff.json --engine-revision <same-commit-SHA>
python chat_handoff.py restore service-handoff.json restored-session.json --engine-revision <same-commit-SHA>
python play.py inspect restored-session.json --actor coordinator
```

Export validates deterministic replay. Verify and restore require matching pinned engine revisions and replay the contained checkpoint; restore refuses to overwrite an existing path. The envelope hash detects incidental corruption, **not deliberate forgery**. Preserve previous handoffs as immutable branches; exporting is not proof that a separate Chat conversation has access to the same file, engine or private sources. No private asset files, source repository snapshots or interpreter environment are bundled.

## Offline Chat runtime transfer

The **Chat runtime bundle** Actions workflow exports a standalone playable public artifact containing `START_HERE.md`, `runner-source.zip`, `ENGINE_REVISION.txt` and `SHA256SUMS`. Prefer retrieving a successful **main** run's artifact directly through the GitHub Connector's artifact download capability into Chat's execution environment. Verify the archive checksum and revision and extract into a fresh execution directory. Manual download/upload is an optional fallback if direct transfer fails. PR runs may use a synthetic merge commit; prefer main for stable provenance. The artifact expires after 14 days. Direct artifact transfer has been demonstrated in ordinary Chat; availability is not guaranteed in every conversation. Never include private sources or sessions in this public workflow.
