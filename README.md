# AGE SimWar Runner

Experimental script-first scenario execution component. Python 3.10+; no dependencies.

**Status:** verified deterministic administrative workflow prototype, not a complete strategic simulation engine. Scheduled world events remain independent of submitted requests. Review-only requests change administrative dispositions; opt-in civilian fixtures can additionally produce bounded request-dependent outcomes. There is no autonomous actor policy, general causal adjudication, live LLM connection or historical reconstruction. See [plan](PLAN.md) for remaining functional work.

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
All three campaign scenarios now have bounded human-directed choices: restoration credits, assistance packages, and independent council consent.

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
