# AGE SimWar Runner — standalone ChatGPT launch

Upload the complete runtime ZIP and paste:

> Start AGE SimWar Runner from the attached ZIP. Follow START_HERE.md and the bundled 00_Meta/CHAT_GAMEPLAY.md. Verify and execute the actual Python engine. Show the bundled playable campaigns and let me select one. Keep gameplay in this conversation. Do not access GitHub or invent results.

## Facilitator procedure

1. Use the actual uploaded bytes. Extract the outer ZIP to a fresh directory only after rejecting absolute paths, traversal, symlinks and duplicate normalized paths. Read ENGINE_REVISION.txt and verify the SHA-256 of runner-source.zip against SHA256SUMS. Safely extract the inner ZIP using the same checks. Checksums establish internal integrity, not publisher authenticity; execute only trusted archives.
2. In the extracted age-simwar-runner directory, read 00_Meta/CHAT_GAMEPLAY.md and run `python game.py list` and `python play.py private bundled-catalog`. Show only executable bundled scenarios; identify strategic rehearsals as unreviewed. Use the returned inventory path with private rehearse for SH44SER. For Great War use its native launcher and guide, select a Deity and seed, and use actor-local packet/choose exchanges. Do not route Great War through private rehearse. Do not fetch external sources or assume private access.
3. Follow framework-specific initialization and turn instructions in CHAT_GAMEPLAY.md. Keep writable sessions outside the engine directory. Preserve the previous verified session before mutation.
4. If verification or execution fails, stop and describe the blocker. Do not replace the engine with prose adjudication.

This offline procedure replaces only the GitHub retrieval steps in CHAT_GAMEPLAY.md. No network or connector is required for the bundled public scenarios.

## Contents

- START_HERE.md: this guide.
- ENGINE_REVISION.txt: exact source revision.
- SHA256SUMS: inner ZIP checksum.
- runner-source.zip: tracked public engine, configuration, tests and documentation.

The public archive contains no private SH44SER sources.

## Authorized private strategic opening archive

A trusted referee may additionally supply a private opening ZIP exported by `python -m age_runtime.core.private_openings export INVENTORY OWNERS ARCHIVE SCENARIO_ID --engine-revision REV`. It is a companion to the exact pinned public runtime ZIP, not a replacement. Use `python -m age_runtime.core.private_openings list ARCHIVE --engine-revision REV` to discover the verified openings. Use `python -m age_runtime.core.private_openings restore ARCHIVE SCENARIO_ID ACTOR SESSION --engine-revision REV` to create a fresh private session outside the runtime. Follow the ordinary private-play procedure. No network or source owner files are needed after export. Only explicitly reviewed fresh standard single-perspective openings without image assets are supported. Keep the archive and session private; integrity checks do not authenticate an untrusted publisher. Do not use this to promote drafts. The seven Conflagration drafts are not yet eligible.
