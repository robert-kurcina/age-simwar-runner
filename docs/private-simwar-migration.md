# Private SimWar package migration

The public runner owns the reusable engine, compilers, adapters, tests and public distribution. The private `vault-sh44ser` owns canonical history, rules and artwork. Reviewed SH44SER scenario configurations, inventory, briefing summaries, source bindings and scenario-specific tests are **private game content**, not public runner source.

## Current inventory and disposition

The private working package is currently at `vault-sh44ser/tools/simwar/private-campaigns/` (23 tracked files on the 2026-11-26 audit). It includes an eight-group inventory, individual scenario-spec.json files, verification scripts, Fiji project alternatives and geographic gallery metadata. The vault also has `.github/workflows/simwar-private-pilot.yml`. PR #993 adds a Fiji-project verifier and extends that workflow.

- **Runner:** generic `age_runtime/core/private_play.py`, source compiler, existing game interfaces, reusable tests and release-time public-package checks. Do not reimplement the scenario-specific scripts as a second engine.
- **Private, local Git-ignored package:** scenario-spec.json, conflagration-inventory.json, authored scenario tests, reviewed briefings, geography manifests and other SH44SER-derived game configuration. Preserve source revision pins and relative package paths.
- **Vault remains authoritative:** narrative history, native mechanics, canonical maps and artwork. The private package references these via exact commits, not by copying them into the public repository.

## Safe transfer: mandatory before deleting anything

1. With a locally authenticated checkout of both repositories, copy `vault-sh44ser/tools/simwar/private-campaigns/` into `age-simwar-runner/private/sh44ser/private-campaigns/`. Keep the nested paths intact. **Do not commit the copy to the runner.**
2. Record the vault commit SHA and a file-by-file SHA-256 manifest outside the public repository. Verify every copied file byte-for-byte. Include PR #993's proposed verifier only if explicitly transferred from its head branch; it is not on vault main.
3. Run the scenario-specific private verification scripts against a pinned checkout of the public runner and the required pinned vault history/artwork revisions. Test the 12-turn Fiji project alternatives, old Fiji pilot, linked recovery, presets, campaign inventory, map gallery and, where available, Chromium smoke test. Re-run replay and visibility checks. The existing private workflow records the exact source pins and commands.
4. Ensure the copy is locally excluded with `git check-ignore -v private/sh44ser/private-campaigns/README.md`. Confirm `git status --short` shows no private content. Inspect `git ls-files private/` and the public ZIP archive to confirm neither includes the private package.
5. Only after checks pass and backup/manifest are independently retained, submit a separate vault PR deleting the migrated `tools/simwar/` tree and its dedicated workflow. If private CI is still needed, move its execution to a **private** deployment context before removing it. Never invoke private tests from public GitHub Actions using privileged secrets.

## Local boundaries

The runtime's existing `private_play` and `source_compiler` accept local inventory/spec paths and authorized source owner root mappings. These are trusted local referee interfaces, not authenticated or sandboxed public services. Keep the approved owner mappings and any generated actor/referee sessions private, outside the public source tree or in ignored `private/`.

Do not copy private scenario files into `campaigns/`, `tests/`, `docs/`, `00_Meta/` or the public runtime ZIP. A Git-ignore pattern only blocks untracked additions; already-tracked content requires separate removal. Public fixtures must remain synthetic.

## PR sequence and exit criteria

1. **Runner boundary PR:** ignore `private/`, document migration and update strategic status. Reuse existing private adapters and add no new universal package framework.
2. **Local migration qualification:** transfer, manifest, execute tests and retain the evidence outside GitHub's public artifacts. Until this succeeds the vault remains the only durable copy.
3. **Vault cleanup PR:** delete the migrated game package and `.github/workflows/simwar-private-pilot.yml` only after safe transfer. Close PR #993 as superseded after carrying its verification logic into the private copy, rather than discarding it.

Historical PRs #977–#992 need no history rewrite. All code and scenario-derived content must be classified by ownership, not merely by file extension. No public PR should expose a private package manifest containing unpublished source excerpts.
