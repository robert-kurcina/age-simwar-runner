# AGE-owned quarterly matrix rehearsal

All engine, campaign, scenario, calibration and testing work belongs to AGE.
Canonical vaults are read-only dependencies. Do not create branches, commits
or pull requests in dependency repositories for AGE work.

The public `scenarios/quarterly-matrix-synthetic.json` is an eight-turn
mechanical rehearsal using anonymous actors and hypothetical values. It is not
a historical opening or an approved historical roster.

## Local historical configuration

Use the existing ignored `private/` directory or an external private workspace
owned by the AGE operator. Keep the historical scenario JSON, assumption
ledger, source mappings and checkpoints there. Never stage these in public Git
or run them in public CI. The runtime accepts an explicit scenario path:

```sh
python -m age_runtime.core.runner private/quarterly-opening.json --validate
python -m age_runtime.core.runner private/quarterly-opening.json private/checkpoint.json --turns 0 --actor PLAYER_ID
```

Supply each model faction choice through the existing faction packet interface.
Use `--turns 0 --request ACTION --actor PLAYER_ID` to register a player order,
then advance after all model actors have decided. Keep referee checkpoints
private. For the public fixture, substitute its path and `patron_a`.

Resolve historical evidence against pinned local vault checkouts or authorized
connector exports using the existing source reader. The general source
compiler currently accepts ISO CE effective dates; do not encode BCE as a
false CE date to bypass that restriction. Until historical date support is
implemented, the explicit historical JSON and a separate provenance/assumption
record are a manual private draft, not a compiled source-qualified snapshot.

The public fixture uses the same accounting and matrix paths as the historical
draft. Its regression test exercises two independent policy sets and eight
turns, replay, reserve conservation, stock nonnegativity and observation
scope. This is mechanical evidence only when tests pass, not historical
validation, balance testing or experiential qualification.
