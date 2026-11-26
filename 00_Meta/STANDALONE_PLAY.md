# AGE SimWar Runner — standalone ChatGPT launch

Upload the complete runtime ZIP and paste:

> Start AGE SimWar Runner from the attached ZIP. Follow START_HERE.md and the bundled 00_Meta/CHAT_GAMEPLAY.md. Verify and execute the actual Python engine. Show the bundled playable campaigns and let me select one. Keep gameplay in this conversation. Do not access GitHub or invent results.

## Facilitator procedure

1. Use the actual uploaded bytes. Extract the outer ZIP to a fresh directory only after rejecting absolute paths, traversal, symlinks and duplicate normalized paths. Read ENGINE_REVISION.txt and verify the SHA-256 of runner-source.zip against SHA256SUMS. Safely extract the inner ZIP using the same checks. Checksums establish internal integrity, not publisher authenticity; execute only trusted archives.
2. In the extracted age-simwar-runner directory, read 00_Meta/CHAT_GAMEPLAY.md and run python game.py list. Show only executable bundled scenarios. Do not fetch external sources or assume private access.
3. Follow framework-specific initialization and turn instructions in CHAT_GAMEPLAY.md. Keep writable sessions outside the engine directory. Preserve the previous verified session before mutation.
4. If verification or execution fails, stop and describe the blocker. Do not replace the engine with prose adjudication.

This offline procedure replaces only the GitHub retrieval steps in CHAT_GAMEPLAY.md. No network or connector is required for the bundled public scenarios.

## Contents

- START_HERE.md: this guide.
- ENGINE_REVISION.txt: exact source revision.
- SHA256SUMS: inner ZIP checksum.
- runner-source.zip: tracked public engine, configuration, tests and documentation.

The public archive contains no private SH44SER sources.
