# AGE SimWar Runner — standalone ChatGPT edition

This archive contains the pinned Python game engine and its public Civic Recovery campaign. No GitHub connection, external server, local installation, or network access is needed to play the bundled campaign. A ChatGPT conversation must support file uploads and Python execution. This archive does not grant access to private campaigns or include private world-building content.

## Start playing

Upload the entire ZIP archive to an ordinary ChatGPT conversation, then enter:

> Start AGE SimWar Runner from the attached ZIP. Follow START_HERE.md, execute the bundled Python engine, and show me the available campaigns, scenarios and participant perspectives. Keep gameplay in this conversation. Do not connect to GitHub or reconstruct the engine in prose.

For a quick game, add: "Start Service Restoration as the coordinator."

## Instructions for the ChatGPT facilitator

1. Use the actual uploaded ZIP bytes in the Python execution environment. Extract the outer archive into a fresh directory after checking member paths are relative, remain inside the destination, and are not symlinks. Read `ENGINE_REVISION.txt` and verify the SHA-256 of `runner-source.zip` against `SHA256SUMS`. Safely extract that inner archive into a fresh directory using the same checks. This checksum establishes internal integrity, not publisher authenticity. Only run archives from a trusted source.
2. In the extracted `age-simwar-runner/` directory, run `python play.py list campaigns/civic-recovery/campaign.json`. Discover supported campaign manifests bundled with the archive. Do not retrieve external repositories or assume access to unbundled private content. Present scenarios, perspectives, and any supported presets from actual configuration. Read the README's facilitator guidance except for GitHub retrieval instructions, which are superseded by this offline launch method.
3. Use the original Python CLI or functions to initialize and inspect the selected scenario. For example, run `python play.py start campaigns/civic-recovery/campaign.json service-restoration /path/to/fresh-session.json` followed by `python play.py inspect /path/to/fresh-session.json --actor coordinator`. Use a fresh writable session path outside the engine directory. Verify checkpoints before each mutation. Present actor-visible objectives, observations, permitted actions and relevant available maps.
4. Interpret natural-language orders into existing allowed actions. Execute only confirmed requests, and advance time only when requested. For example, when explicitly confirmed, run `python play.py submit /path/to/fresh-session.json restore_service_center --actor coordinator` then `python play.py advance /path/to/fresh-session.json --actor coordinator`. Preserve the previous verified session before mutation and bind each decision to the current session revision. Do not substitute model-generated state or reconstructed adjudication. Use the existing continuity functions for linked scenarios.
5. Present actual engine output, not hidden state; distinguish narrative from adjudication and label illustrative quantities. Keep the active session inside the conversation. File downloads and cross-thread resumption are optional. If Python execution or verification fails, stop and report the precise blocker rather than claiming a result.

## Package layout

- `START_HERE.md`: this document and launch prompt.
- `ENGINE_REVISION.txt`: exact Git commit of the bundled engine.
- `SHA256SUMS`: checksum of the inner source archive.
- `runner-source.zip`: unchanged tracked engine source, public scenario configurations, documentation and tests.

The bundled campaign is an illustrative civilian recovery and institutional coordination simulation, not a complete strategic combat or historically calibrated predictive engine. Private packages require a separate authorized distribution containing the necessary scenario inputs and artwork; do not assume a private source reference can resolve offline.
