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
