# Great War — Manafount rehearsal

Unreviewed mechanics pilot; no historical or balanced scenario claim. Source: vault-great-war revision da7e1140e92d5450fd82393acc2a15a3ff36a037, core_rules/00_DEITY_CENTRIC_CONTINUOUS_PLAY.md, core_rules/13_MANAFOUNTS.md, cards/EVENT_CARD_GRAMMAR.md and deities/PROMINENCE_AND_MANIFESTATION.md. The two placeholder Deities, regional hex IDs, hand size, seeded deck, Event mix and one symbol per year are illustrative. No PR, Nation simulation, military adjudication, VP or canonical deity identities.

Run from the runner root:
```sh
python -m age_runtime.core.great_war start /tmp/gw.json --seed 42
python -m age_runtime.core.great_war observe /tmp/gw.json amber
python -m age_runtime.core.great_war play /tmp/gw.json amber REV /tmp/command.json
```

A command is {"card":"event-00","tap":null} or a card from the current hand with a tap object {"fount":"event-00","pile":"amber_n","disposition":"N1"}. Select eligible local source and pile; hidden first tap disposition is a legal regional hex or "remove"; public taps use null. Reveal is public and not owned. A card can establish a Fount before its optional Tap; only one Tap per Deity/Region between Time! advances. Hidden Events remain face up, public sources recharge on Time!, drained public sources can be destroyed by a second eligible tap. Other hands and exact opposing PL are concealed. The facilitator separately obtains each active Deity's choice, verifies revision and presents only its own observation. Full checkpoint is referee-only. No winner is adjudicated: stop at five years or exhausted pool, report actual state. No network required.

## Deity decision exchange

Run `python -m age_runtime.core.great_war packet SESSION ACTOR` for the current active Deity. The packet contains only actor-local observations and validated commands, with zero-based choice indices. Supply a JSON response containing exactly `packet_id` and integer `choice` to `python -m age_runtime.core.great_war choose SESSION ACTOR RESPONSE`. Recompute the packet before applying; stale, wrong-actor and out-of-range choices fail without committing. Do not supply another Deity's private hand or exact PL to the deciding model. Recent public Plays supply contextual reminders. A required icon without any legal target is not offered; if no legal card remains, stop and report the unresolved native fallback rule rather than inventing a pass. Model decisions are external to the engine; scripted CI does not establish independent LLM quality.
