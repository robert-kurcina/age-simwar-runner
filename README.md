# AGE SimWar Runner

Experimental script-first scenario execution component. Python 3.10+; no dependencies.

**Status:** verified deterministic administrative workflow prototype, not a complete strategic simulation engine. Scheduled world events remain independent of submitted requests. Request reviews change administrative dispositions only. There is no autonomous actor policy, general causal adjudication, live LLM connection or historical reconstruction. See [plan](PLAN.md) for remaining functional work.

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

See [scenario configuration](docs/scenario-format.md). Use `python runner.py path/to/scenario.json --validate` before starting a local session. The supported contract remains scheduled events and administrative review.

## Compare completed sessions

The existing CLI supports manual interaction through request submission, actor inspection and turn advancement. Use separate fresh checkpoint paths for independent sessions:

```sh
python runner.py scenarios/demo.json baseline.json --turns 2
python runner.py scenarios/demo.json alternative.json --actor library --request request_room_inspection --turns 0
python runner.py scenarios/demo.json alternative.json --turns 2
python comparison.py scenarios/demo.json baseline.json alternative.json
```

The comparison is read-only and requires completed checkpoints from the same scenario revision. It reports actual state, milestone results, objective status and administrative request counts. Differences are descriptive, not evidence of causation.

## Verification

`python -m unittest -v`

See [architecture](docs/architecture.md) and [plan](PLAN.md). Public synthetic scenarios only; private scenario packages stay external.

Development provenance and LLM guidance: [00_Meta](00_Meta/).
