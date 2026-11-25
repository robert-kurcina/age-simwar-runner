# AGE SimWar Runner

Experimental script-first scenario execution component. Python 3.10+; no dependencies.

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

## Verification

`python -m unittest -v`

See [architecture](docs/architecture.md) and [plan](PLAN.md). Public synthetic scenarios only; private scenario packages stay external.

Development provenance and LLM guidance: [00_Meta](00_Meta/).
