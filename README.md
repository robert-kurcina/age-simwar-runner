# AGE SimWar Runner

Experimental script-first scenario execution component. Python 3.10+; no dependencies.

## Demonstration

Run from the repository root using a fresh checkpoint path:

```sh
python runner.py scenarios/demo.json checkpoint.json --turns 0
python runner.py scenarios/demo.json checkpoint.json --actor library --request request_room_inspection --turns 0
python runner.py scenarios/demo.json checkpoint.json --turns 1
python runner.py scenarios/demo.json checkpoint.json --inspect --actor library
python runner.py scenarios/demo.json checkpoint.json --inspect --actor maintenance
python runner.py scenarios/demo.json checkpoint.json --turns 1
```

The library sees delayed availability reports while maintenance sees current values. Requests are recorded but do not execute effects. The referee owns the checkpoint; actor output is a logical projection, not access control. Use a fresh path for another run. Unsupported checkpoint versions and changed scenarios are rejected.

## Verification

`python -m unittest -v`

See [architecture](docs/architecture.md) and [plan](PLAN.md). Public synthetic scenarios only; private scenario packages stay external.

Development provenance and LLM guidance: [00_Meta](00_Meta/).
