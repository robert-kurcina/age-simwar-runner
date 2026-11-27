# CLI operations

Run commands from the repository root.

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

See [scenario configuration](./scenario-format.md). Use `python runner.py path/to/scenario.json --validate` before starting a local session. The supported contract is scheduled events, administrative review and three opt-in synthetic civilian rules.

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

See [architecture](./architecture.md) and [plan](../PLAN.md). Public synthetic scenarios only; private scenario packages stay external.

Development provenance and LLM guidance: [00_Meta](../00_Meta/).

## Pinned source compilation

See [source compiler](./source-compiler.md). A trusted local operator can resolve reviewed structured initial-state values from allowlisted Git repositories and produce a standalone scenario plus provenance snapshot. Existing runner and checkpoint formats are unchanged.

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

The **Chat runtime bundle** Actions workflow exports the tested public tracked source as an artifact containing `runner-source.zip`, `ENGINE_REVISION.txt` and `SHA256SUMS`. Prefer retrieving a successful **main** run's artifact directly through the GitHub Connector's artifact download capability into Chat's execution environment. Verify the archive checksum and revision and extract into a fresh execution directory. Manual download/upload is an optional fallback if direct transfer fails. PR runs may use a synthetic merge commit; prefer main for stable provenance. The artifact expires after 14 days. Direct artifact transfer has been demonstrated in ordinary Chat; availability is not guaranteed in every conversation. Never include private sources or sessions in this public workflow.

## Private diplomatic deliberation (opt-in)

When the strategic scenario enables `diplomatic_history`, the trusted referee may record an actual actor's private intention or relationship assessment without making a public statement or spending a turn:

```sh
python play.py private record-diplomacy SESSION ACTOR RECORD.json --revision REVISION
```

An intention record has exactly kind (intention), id, counterpart, topic, text, status (active or withdrawn), and revises (null initially, then the latest own claim ID or private record ID for the same counterpart/topic). Private record IDs are unique within their actor's history; do not reuse them as that actor's communication IDs. A relationship assessment uses kind (assessment), id, counterpart, topic, text, revises and basis instead of status. Basis is a nonempty list of objects with kind (communications, proposals or agreements) and id (the corresponding actor-visible record ID). The engine captures the dated evidence snapshot; do not provide an evidence field. Outgoing dispatch and unanswered own proposals do not establish counterpart conduct. A received statement is not proof of its truth, and expiry or unsigned commitments do not prove intent. Use the actor's actual authorized deliberation, not invented player thoughts. Neither record establishes consent, authority, fulfillment, objective truth or mechanical effects. Use the returned revision. The actor-local diplomatic history and institutional memory expose these records only to their owner; referee checkpoint access remains privileged.

## Scoped strategic establishment (opt-in)

For a scenario with strategic_establishment: true, a trusted referee may use:

```sh
python play.py private establish-context SESSION RECORD.json --revision REVISION
```

A record contains exactly one of details or changes, each a list of 1–12 entries. A detail contains id (inc: followed by a lowercase identifier), kind (setting_detail, facility_detail or administrative_detail), label, description, audience (nonempty list of existing actor IDs), and basis (referee rationale). A change contains id, before (exact current description), after and basis. Audience and identity are immutable. The engine preserves original establishment and revision provenance; actor views exclude rationale and other audience identities. Full institutional memory includes only actor-visible context. Descriptions are session-specific presentation facts, not new canon, discovered evidence, capabilities, assets, authority, permissions, consent, or mechanical changes. A facility detail cannot make a facility operational; use existing project and commitment mechanics for material consequences. The referee verifies plausibility, historical fidelity and semantic limits before submission. Rejected batches change nothing. Use the returned revision; no Turn or Critical Decision is consumed.

## Scoped institutional permissions (opt-in)

Enable dynamic_negotiation and define permission_terms as a scenario-reviewed mapping from term ID to issuer, grantee, description and max_due_minute (a Turn boundary). Both parties can inspect their own terms. Use the existing negotiate or faction-choice command; permission proposals contain kind (propose or counter), id, recipient, permission (term ID), and due_minute (no later than the authored limit); counter also requires parent. Do not mix transfer and permission terms in the same proposal or counter family. Either party can propose, but only the actual recipient can accept or reject. Acceptance activates the scoped permission immediately, not its exercise. The proposer may withdraw a pending permission, the issuer may revoke an active permission, and the grantee may release it. These commands have exactly kind (withdraw, revoke, release) and id. Unresolved proposals and active permissions expire at the due boundary. Use distinct proposal IDs; equivalent open terms are rejected. No automatic inspection, disclosure, resource transfer, objective achievement or fulfillment follows from permission. Existing actor routing, revision checks, decision pacing, and one model choice per Turn still apply. The trusted referee confirms the actual actor's decision and uses only reviewed authority; do not infer consent from dialogue or private intent.

## Reviewed eligible developments (opt-in)

For a reviewed civilian project scenario, event_templates maps IDs to description, participant, audience, requires (current participant property thresholds), permission (reviewed term ID or null), and outcome (dedicated initially-zero property visible to exactly the audience). No arbitrary effects or generated findings. A template needs a permission or nonempty thresholds. Schedule using:

```sh
python play.py private schedule-development SESSION RECORD.json --revision REVISION
```

The record contains exactly template, due_minute, permission_id (specific active negotiation proposal ID, or null for a permission-free template), and rationale. The due minute must be a future Turn boundary strictly before permission expiry. Selection requires current eligibility; the engine rechecks thresholds and the exact permission at resolution, after review and negotiation settlement. Revocation or release blocks completion even if a new permission is subsequently granted. Each template can be selected once; no retry or automatic selection. A completed development changes only its dedicated outcome flag from zero to one. The description becomes visible when the actor's outcome report arrives; pending and failed developments and referee rationale are not disclosed. A completed inspection is not a finding or grant approval. The referee validates contextual plausibility and actual authority, and must not schedule developments merely to force a desired narrative.
