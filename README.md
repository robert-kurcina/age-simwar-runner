# AGE SimWar Runner

Play scenario-based games in a single ChatGPT conversation. ChatGPT presents the story and interprets your decisions; the bundled Python engine resolves actions and maintains authoritative game state.

## 1. Choose how to play

| Method | Requirements |
| --- | --- |
| GitHub-connected | Active GitHub connector with repository access, plus Python execution |
| Standalone ZIP | Uploaded runtime archive, plus Python execution; no GitHub connection |

No local installation or hosted game server is required for Chat play. Keep playing in the same conversation.

### A. GitHub-connected play

Activate your GitHub connector in a new ChatGPT conversation and paste:

```text
Retrieve robert-kurcina/age-simwar-runner using my GitHub connector.
Follow README.md and 00_Meta/CHAT_GAMEPLAY.md.
Load and verify the actual Python runtime, show available authorized
campaigns and playable scenarios, and let me select one.
Execute my confirmed decisions using the engine in this conversation.
Do not invent engine results or reveal hidden scenario information.
```

Private SH44SER content requires separate authorized access and a supported runtime package.

### B. Standalone ZIP play

1. Download a successful [Chat runtime bundle](https://github.com/robert-kurcina/age-simwar-runner/actions/workflows/chat-runtime-bundle.yml) artifact from GitHub Actions. Choose a main-branch build when available. The download is a ZIP; keep it intact.
2. Upload the ZIP to a new ChatGPT conversation.
3. Paste:

```text
Start AGE SimWar Runner from the attached ZIP. Follow START_HERE.md
and the bundled 00_Meta/CHAT_GAMEPLAY.md. Verify and execute the actual
Python engine. Show the bundled playable campaigns and let me select one.
Keep gameplay in this conversation. Do not access GitHub or invent results.
```

The updated archive includes START_HERE.md; older artifacts without it use the bundled README and facilitator guide with the offline procedure. The public archive does not include private SH44SER material.

## 2. Choose a campaign

| Campaign / scenario | Status |
| --- | --- |
| Civic Recovery — Service Restoration | Playable demonstration |
| Civic Recovery — Service Review | Playable demonstration |
| Civic Recovery — Community Assistance | Playable demonstration |
| Civic Recovery — Civic Agreement | Playable demonstration |
| Fear! — The Boothbay Incident | Bounded DXD trial |
| Fear! — The Salt-Stained Silence (Castine) | Bounded investigation trial; full source arc not implemented |
| Fear! — The Keeper at Ram Island | Executable bounded DXD trial |
| Conflagration / SH44SER | Seven unreviewed regional rehearsals; reviewed private distribution pending |

| Near Melanesia — Production Accord (2044) | One unreviewed industrial rehearsal; four perspectives |

| Great War — Manafount rehearsal | Unreviewed native Deity/Event pilot; two perspectives |

The live catalogs are authoritative: run `python game.py list` and `python play.py private bundled-catalog` in the extracted repository. For SH44SER use the returned inventory, episode ID and selected actor with `private rehearse`. For Great War use its returned launcher and guide; its clock is Event-driven, not fixed-interval. Do not imply canonical approval. Do not offer imported scenarios as playable.

For a first narrative game, choose **The Boothbay Incident**. Boothbay supports advanced GM operations; Castine and Ram Island use authored-action adjudication with persistent local narrative continuity. See the [current narrative facilitator protocol](00_Meta/NARRATIVE_GM.md). Narrative trials are mechanically supported but current player-led experiential qualification is pending; see [qualification procedure](docs/narrative-chat-play-qualification.md). For a short strategic demonstration, choose **Service Restoration** as coordinator.

## 3. Play

Choose an offered action or describe your intended action in ordinary language. ChatGPT maps it to a permitted engine action, asks for confirmation when ambiguous, and presents the actual result. Time-bearing Mythos actions advance the clock; read-only recall and inspection do not. Strategic turns advance when requested. Hidden information is revealed only when earned. If the engine cannot execute or verify the session, gameplay stops rather than switching to invented adjudication.

## 4. Distributions

| Intended archive | Contents | Status |
| --- | --- | --- |
| age-simwar-standalone.zip | Public engine, Civic Recovery and Mythos | Public runtime artifact available; updated standalone guide included by new builds |
| age-simwar-sh44ser.zip | Supported private SH44SER campaigns | Pending |
| age-simwar-conflagration.zip | Full runtime with Conflagration-specific launch guide and seven draft episodes | Draft artifact `conflagration-draft-REV` on successful bundle build; reviewed distribution pending |

GitHub Actions uses revision-specific artifact names; the intended archive names describe distribution scope, not a permanent release URL.

## 5. Developer reference

Python 3.10+, standard library only. Run commands from the repository root.

```sh
python game.py list
python game.py describe mythos boothbay
python game.py describe civic-recovery service-restoration
python -m unittest discover -v
```

| Directory | Purpose |
| --- | --- |
| [00_Meta/](00_Meta/) | LLM gameplay/development guidance and provenance |
| age_runtime/core/ | Strategic engine and session management |
| age_runtime/mythos/ | Character-oriented gameplay |
| age_runtime/interfaces/ | Narrative, maps and model interfaces |
| age_runtime/examples/ | Demonstration implementations |
| campaigns/, frameworks/, scenarios/ | Authored configurations and trial overlays |
| tests/ | Regression tests |
| [docs/](docs/) | Technical documentation |

Root Python files preserve existing launch commands. See [CLI operations](docs/cli.md), [architecture](docs/architecture.md), [facilitator guidance](00_Meta/CHAT_GAMEPLAY.md) and [PLAN.md](PLAN.md).

This is an experimental game engine, not a calibrated predictive simulation. Strategic execution is limited to supported civilian and institutional scenarios. Mythos scoring and narrative branches remain provisional.

The `describe` command provides the common scenario profile (scale, perspective, actual duration and conclusion mode). [Scenario generation guidance](00_Meta/SCENARIO_GENERATION.md) defines the proposed authoring process; automatic generation and new mechanics are not yet implemented.
