# Local source compiler v1

The operator supplies a local JSON owner-to-Git-root allowlist. No network access is needed. Owner identity is an operator assertion; the compiler verifies commit objects and content, not repository authorship.

A source file contains reviewed structured records, for example:

```json
{"entities":{"municipality":{"fields":{"credits":{"value":2,"effective_date":"2003-04-01","classification":"canonical"}}}}}
```

A compiler specification contains version (1), effective_date, scenario (ordinary runner configuration with referenced initial keys omitted), and initial_refs (map from initial key to reference). Each reference contains owner, revision (full 40-character commit SHA), path (relative JSON path), entity, field, effective_date, classification. Only nonnegative integer values are supported; the effective date must exactly match the scenario and source record. Classifications: historical, canonical, derived, estimated, hypothetical. Unresolved required values fail. Literal/reference collisions fail instead of silently overriding.

Run:

    python source_compiler.py spec.json owners.json snapshot.json compiled-scenario.json
    python runner.py compiled-scenario.json session.json --turns 0

Both outputs must be new, distinct files. Retain the provenance snapshot with the session. The existing runner pins the compiled scenario by digest; the compiler does not enforce filesystem immutability. The Python stale_dependencies function compares source file bytes with committed local HEAD, not uncommitted edits. File-level changes may conservatively flag unchanged fields. This increment does not implement Markdown/SQLite extraction, automatic source refresh, optional unknowns, cross-source semantic conflict detection, scenario variation inheritance or recursive campaign provenance. Public tests use temporary synthetic Git repositories only.

## Bounded civilian scenario variations

Pass `--variation variation.json` to the compiler CLI. A variation contains version (1), id (lowercase letters, digits and hyphens), base_digest (runner.digest of the base specification), initial_overrides, and report_delays. Both maps may be empty. Each initial override contains value (nonnegative integer) and reason (nonempty text). Only restoration_credits in service-restoration and aid_packages in community-assistance can be overridden. Overrides are hypothetical, not edits to source facts. report_delays maps actor IDs to visible-variable names and nonnegative integer delay minutes. Civic agreement supports reporting delays only. The output retains base dependencies and records original and overridden values, variation digest and a distinct scenario ID/digest. Base specs remain unchanged. Variations currently execute as independent scenarios; campaign continuity mappings still require catalog scenario identities. No arbitrary rule, event, objective or permission overrides are supported.

## Narrative evidence

Optional evidence_refs maps IDs to references containing owner, revision, path (Markdown), heading (unique exact ATX heading), reviewed_for (scenario date), and classification (canonical or historical). At least one numeric or narrative reference is required. The compiler records file and section digests, not prose. The review date is a human assertion of relevance, not proof that the section describes that date. Evidence does not populate numeric values or validate the historical accuracy of scenario literals; maintain scenario assumptions separately. Evidence staleness is reported with an evidence: prefix. Duplicate headings fail. No automatic prose interpretation.

## Connector-backed pinned sources

The owner allowlist also accepts an inline connector export instead of a local Git root. For each required reference, the trusted facilitator retrieves the exact repository file at its full commit SHA using the authenticated connector, requesting base64 bytes and the returned Git blob SHA. Remove base64 line wrapping only (do not rewrite source text). Supply the actual bytes in a private owners JSON file:

```json
{"example":{"kind":"connector-export-v1","files":[{"revision":"<40-character commit SHA>","path":"facts.json","blob_sha":"<returned 40-character blob SHA>","content_base64":"<exact base64 bytes>"}]}}
```

Use the existing compiler, private start, participant profile and image-map entry points. Each owner may use either a local Git root or a connector export. Missing/duplicate revision-path bindings and byte/hash mismatches fail closed. Snapshot formats and content/section digests remain identical. This is a trusted facilitator transport, not a cryptographic proof of a commit's tree membership: the connector supplies the commit/path binding, and the runtime independently checks the blob bytes. Never manufacture a blob SHA from altered text or use a mutable branch in place of the requested revision. Connector exports have no local HEAD; stale_dependencies explicitly rejects them rather than pretending freshness. Keep exports private and temporary; do not publish them or embed them in public bundles. Large or unavailable assets remain a transfer limitation.

## Selective runner-owned resource acquisition

Run `python -m age_runtime.core.resource_acquisition INVENTORY` to enumerate deduplicated owner/commit/path requirements and use sites from the explicit compiler references, faction property references and reviewed image maps in a strategic inventory. With an existing authorized owners mapping, add `--owners OWNERS` to check actual bytes through the existing pinned-source reader and report SHA-256 digests and lengths. This is discovery and verification, not a connector downloader, semantic review or compilation. Then use the existing compiler and draft catalog compilation. Do not move execution to a vault or publish source exports. Additional runtime context must be separately authorized and pinned; it does not directly change mechanical state.

## Optional network-enabled GitHub provider

In a trusted network-enabled runner environment, set `GH_TOKEN` privately to an authorized read-only GitHub credential. Run `python -m age_runtime.core.github_resources INVENTORY /private/path/owners.json --allow-owner OWNER/REPO` (repeat the allow-owner flag for each required repository). This retrieves only explicit pinned files using GitHub's contents API, refuses redirects and unapproved repositories, verifies Git blob bytes through the existing reader, and writes a new private connector-export-v1 mapping. The credential is not stored in the mapping. Keep the file outside Git checkouts; remove it after compilation. API file-size limits and Git LFS may prevent acquisition; use an authorized pinned local Git checkout instead. This is optional transport, not a mandatory service or a workaround for a network-disabled Chat runtime. Run the existing draft compiler with the resulting owners file. Do not put credentials or source bytes into public CI or logs.

## Unified preparation diagnostics

Run `python -m age_runtime.core.scenario_preparation INVENTORY [--owners OWNERS]` to inspect roster/profile presence, resource requirements, draft rehearsal opening verification and optional compilation and reviewed opening verification. Without owners, source checks remain not-checked; missing source bytes do not prevent self-contained rehearsals. Catalog review status is not promoted by any check. This report tests fresh standard openings only, not continuity, variants, full gameplay or semantic canon approval. It writes no files; use the existing compiler and distribution commands for actual output. Keep reports containing private scenario metadata private.
