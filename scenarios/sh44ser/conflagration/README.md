# Conflagration draft scenario configurations

Runner-owned, minimal hypothetical exercise data grounded in pinned SH44SER references. The source vault remains read-only; no source bytes or complete lore are included. All seven episodes are draft-unreviewed and must not be offered as reviewed playable selections. Hexaday is catalog-only historical context.

## Imported v7 baseline (historical provenance, not current hashes)

Original archive SHA-256: `5f5bc2f6214b3686fdb3dfd0aab5e172978baa67744cb2da4d160c465ea7baa6`. At migration in PR #197, each imported specification matched the original archive's Git blob SHA exactly. The archive's embedded faction profiles are the authoritative draft configuration; do not duplicate them into separate files. The WPC candidate is retained separately and is not a selectable faction.

| Group | Imported specification blob |
|---|---|
| Disaster Response | `d2e4180271d4555e6fefa2d4d0174e1bd82168a1` |
| Fallout | `8b9e1d4434e43a5192b2446f563ee72c5d3fd00f` |
| Mainlander Ingress | `199f85e82c15f8a10132d2f26c695668c541f01b` |
| Early Reconstruction | `487e43150cb1839e135b254f5452b74253e1ce54` |
| Purge | `422091a856d41b64ef9698bad81b573981cea5da` |
| Agreement | `657a824f042cb05affd143dc763652046c903368` |
| Reconstruction | `b9e8b68522200bde8cc60ca65446462db245eeb9` |

The catalog relocates the original specification paths into phase directories and adds the historical-only Hexaday group; its existing seven entry statuses and perspective lists remain unchanged.

## Qualification

Run `python -m unittest -v tests.test_conflagration_drafts` from the runner root. The tests exercise raw scenario validation, 25 selectable perspectives, terminal checkpoint replay, draft selection rejection, and the v6/v7 Fallout and RWF divergent decision routes. They do not require access to private canon, and they do not test independent LLM judgment or establish source-backed compilation. Historical rehearsal result files remain historical evidence, not current golden checkpoints.

All eight distinct source files (including the unbound WPC candidate's evidence) were retrieved at revision `c918766d434453644a137cfadfa901f4a8be96b5`, their base64-decoded bytes matched the returned Git blob SHA, and all 15 distinct referenced headings occurred uniquely outside fenced code. This connector preflight is not the Python compiler. Use the existing source compiler with authorized owners and private output paths for actual pinned-source compilation. Do not promote drafts until the compiled configurations and scenarios are reviewed. Hypothetical quantities are not canonical statistics; agreement flags are commitments, not actual legal judgments or historical outcomes.

Future changes should be ordinary runner commits, with ZIPs generated only for distribution. No separate content repository or new loader.

## Dated grounding review

ST-B revises opening context and delegated authority across the seven drafts without changing initial state, project definitions, actions, resource transfers, agreement prerequisites, evidence references or faction identities. The Arabian religious delegation's priority order is an illustrative design choice, not historical policy. The WPC candidate remains unbound. Actual source-backed compilation and reviewed registration remain pending.

## Collective source compilation

Use the shared draft-catalog entry point from the runner root with an already authorized owners mapping (local Git roots or connector-export-v1 records):

```sh
python -m age_runtime.core.draft_compilation \
  scenarios/sh44ser/conflagration/inventory.json \
  /private/owners.json /private/new-compiled-output
```

The destination must be new and outside the runner, catalog and local source checkouts. All entries must be drafts; every scenario compiles using the existing pinned-source compiler, checks its identity and supported mechanics, and verifies an opening checkpoint for each eligible perspective. Only after all entries pass are snapshots and a digest report written, with restrictive local permissions. The report is not a play registration or authorization to distribute output. Source bytes are not written to the output. CI uses explicitly synthetic evidence identities and bytes, not private vault content; actual canonical compilation remains separate. No live vault access is required to inspect an already compiled snapshot.

## Strategic interaction refinement

Five additional episodes now use existing scoped communications, propositions, diplomatic history and descriptive establishment. Mainlander Ingress permits a consented review of anonymized aggregate procedures only; the separate completion flag is not an individual legal decision. Purge and Agreement support bounded voluntary consultation permissions independent of collective assent. Reporting delays are illustrative exercise assumptions. Fallout and Early Reconstruction preserve their previously qualified routes. All entries remain drafts. CI and actual source compilation are separate gates.

## Contrasting outcome qualification

Run `python -m unittest -v tests.test_conflagration_outcomes` alongside the existing draft regressions. The scripted routes exercise alternative relief investments, grants, multiple capacity bottlenecks and independent institutional consent through terminal checkpoints. These are mechanical outcome tests, not historical predictions or independent LLM gameplay qualification.

## Contextual decision support

The strategic private-play CLI provides `decision-brief SESSION` as a read-only actor-scoped projection of current goals, options, tradeoffs, report uncertainty, recent decisions and commitments. Retrieve older relevant records using `memory SESSION` (optionally `--counterpart ID`). The brief is guidance, not an adjudication or automatic decision; preserve actual player consent and independent faction exchanges. No extra state or decision expenditure for reading.
