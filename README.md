# AGE SimWar Runner

A prompt-driven scenario simulation component of AGE. Play within a single ordinary ChatGPT conversation using the GitHub Connector and the authoritative Python runner (Python 3.10+, standard library only).

## Quick start — play in ChatGPT

### Prerequisites

- Your ChatGPT account has the GitHub Connector configured and active, with access to `robert-kurcina/age-simwar-runner`.
- The current conversation can invoke that connector and execute Python code.
- For private campaigns, your connected account also has access to the relevant private campaign and canonical source repositories. Public fixtures require no private access.

No local installation, hosted game server, MCP service, or manual checkpoint transfer is required for the intended single-conversation experience. Connector capabilities may vary by conversation; repository read access alone does not establish runtime execution capability.

### Launch prompt

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

### Facilitator instructions

See [00_Meta/CHAT_GAMEPLAY.md](00_Meta/CHAT_GAMEPLAY.md) for the authoritative LLM gameplay procedure and framework-specific guidance.

**Current status:** The public runtime archive was successfully transferred into ordinary Chat and the pinned Python engine passed 68 regression tests there. The public opening and subsequent gameplay were demonstrated; the full private campaign prompt-to-play workflow remains to be qualified. Supported executable scope is civilian recovery and institutional coordination, not operational combat adjudication or predictive historical simulation. See [PLAN.md](PLAN.md).

## Experimental Mythos campaign

Run `python game.py list` to discover bundled campaigns and their implementation status. Strategic scenarios continue to use `play.py`; the Mythos trial uses `game.py`. Boothbay is a bounded investigation trial, not the full AIMythos ruleset. Castine and Ram Island are preserved but not yet executable.

```sh
python game.py start boothbay /tmp/boothbay-session.json --seed 42
python game.py inspect /tmp/boothbay-session.json
python game.py act /tmp/boothbay-session.json inspect_docks --revision <revision-from-inspect>
```

See [Mythos gameplay guidance](00_Meta/CHAT_GAMEPLAY.md#mythos) for current trial limits and presentation rules.

## Repository organization

- `age_runtime/core/`: strategic simulation, session management and source compilation.
- `age_runtime/mythos/`: character-oriented gameplay and bundled catalog.
- `age_runtime/interfaces/`: narrative, models, maps and presentation.
- `age_runtime/examples/`: demonstration implementations.
- `campaigns/`, `frameworks/`, `scenarios/`: configuration data.
- `tests/`: regression tests (`python -m unittest discover -v`).
- `00_Meta/`: LLM development and gameplay guidance, provenance.
- `docs/`: technical references, including [CLI operations](docs/cli.md).

Run commands from the repository root. Root Python files are compatibility entry points, not primary implementations.
