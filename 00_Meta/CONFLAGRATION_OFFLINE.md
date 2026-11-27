# Conflagration — standalone draft campaign

Upload the complete Conflagration draft ZIP to a new ChatGPT conversation and paste:

> Start Conflagration from this ZIP. Follow START_HERE.md. Verify and execute the actual Python engine, show the Conflagration episodes and selectable factions, and let me choose. Keep gameplay in this conversation. Do not access GitHub or invent engine results.

## Facilitator

1. Follow the safe extraction and checksum verification procedure in the bundled `00_Meta/STANDALONE_PLAY.md`. The outer archive contains ENGINE_REVISION.txt, SHA256SUMS, runner-source.zip and this launch guide. Use a trusted archive only.
2. From the extracted runner root, read `00_Meta/CHAT_GAMEPLAY.md`. Run `python play.py private discover scenarios/sh44ser/conflagration/inventory.json`. Present only available episodes and perspectives; Hexaday is context-only.
3. After the player selects, run `python play.py private rehearse scenarios/sh44ser/conflagration/inventory.json SCENARIO ACTOR SESSION` with a fresh session path outside the runtime. Use `--opportunity-latitude` only if the player selects a different setting.
4. Use the ordinary private strategic decision brief, confirmed decision, actor-local faction exchange, and turn resolution commands. Preserve checkpoints; do not reveal private faction state. No connector, source owner mapping or network is required.
5. All seven episodes are **unreviewed illustrative rehearsals**. They are independent episodes, not an automatically linked campaign. Pinned evidence references are not verified by this offline workflow. Do not promote drafts or infer canonical facts. Stop if verification or execution fails.

This campaign-specific launch artifact reuses the exact full runner-source ZIP; it does not strip other engine modules or bundled examples. It contains the tracked runner draft configurations, not the private vault source bytes or reviewed private opening exports. The reviewed distribution remains a separate authorized procedure.
