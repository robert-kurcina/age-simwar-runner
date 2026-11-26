# Scenario configuration (v1)

The runner accepts local JSON files. The bundled library reopening example is
the reference. Configuration describes scheduled observations and administrative
review, not autonomous behavior or a validated real-world model.

Required top-level fields:

| Field | Meaning |
|---|---|
| version | Integer 1 |
| id | Nonempty scenario identifier |
| turn_minutes | Positive integer duration |
| end_minute | Positive integer horizon |
| initial | Map of named integer values at minute zero |
| events | Array of scheduled updates |
| constraints | Array of milestone checks |

Each event has a unique string id, minute (1 through end_minute), key
(from initial), and integer delta. At equal times, events execute in input
order before milestone checks. Each constraint has minute, key and integer
equals; failure is recorded rather than corrected.

Optional fields:

- actors: map of actor IDs to label, objectives, visible_keys and
  report_delay_minutes. Each objective has description, key, comparison
  (at_least, at_most, equal) and integer threshold. Visibility defaults
  to none. Report delays default to zero and apply only to visible keys.
- action_catalog: map of administrative request names to description and
  allowed actors. Requests are recorded; only the opt-in restoration rule can fulfill a request.
- administrative_reviews_per_turn: nonnegative integer, default zero.
- service_restoration: optional literal true, enabling the synthetic public-service rule. Requires nonnegative integer open_service_centers and restoration_credits and a restore_service_center action. Scheduled events cannot change credits or close centers. Each reviewed restoration request spends one credit and opens one center, or records insufficient_credits. Effects occur at the turn boundary after scheduled updates and before checks. Other requests remain review-only.

Validate a scenario without creating a checkpoint:

    python runner.py scenarios/demo.json --validate

Run a scenario with a fresh checkpoint:

    python runner.py scenarios/demo.json checkpoint.json --turns 2

Checkpoints pin the scenario content by digest. Changing scenario data requires
a new checkpoint; no automatic migration is performed. The interpretation
exchange remains restricted to the bundled library demonstration. Actor
projections are not filesystem access control.
