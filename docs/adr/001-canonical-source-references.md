# ADR-001: Canonical source references and compiled snapshots

Status: accepted by author, 2026-11-25. Implementation pending.

## Decision

Authoritative world-building repositories own canonical facts. Scenario packages reference those facts rather than maintain independent manual copies. Historical evidence retains its own provenance. Scenario packages own simulation-specific abstractions, objectives, approved assumptions, variations and continuity mappings. The runner consumes validated generated snapshots, not unrestricted corpus prose.

At authoring time a reference may track a selected revision. At compilation it must resolve to an immutable revision, source path, stable selector and effective date, with a content digest. A source value must distinguish historical, canonical, derived, estimated, hypothetical and unresolved claims. Use the existing canonical ownership map; do not introduce a competing database. A later-era value is not a historical baseline. Political entity mappings across eras require explicit review.

The compiler records material dependencies, compiler/schema versions and approved overrides. Ambiguity, missing required facts, incompatible dates and unresolved conflicts fail compilation; optional unknowns remain explicit. LLM-assisted extraction is a proposal, not authoritative data. Generated snapshots are immutable during a session; new source revisions flag dependent drafts/snapshots for explicit recompilation, never silently alter an active or completed session.

## Boundaries

Keep private source paths, content, scenario packages, generated private snapshots and credentials out of public source control and public CI. Public tests use synthetic sources. Initially prefer local read-only resolution with no automatic network fetching. No general rule language, database migration or bulk dossier restructuring is authorized by this ADR.

## Alternatives

Manual copies risk drift. Floating references alone undermine replay. Pinned references alone require source availability at runtime. Generated pinned snapshots preserve both reproducibility and source ownership, at the cost of storage and explicit recompilation.

## Acceptance

Compile the same pinned synthetic inputs twice with identical results; reject missing/ambiguous references and temporal conflicts; detect source changes without modifying previous snapshots; preserve reviewed provenance and independently executable runner input. Qualify one private civilian scenario separately before asserting coverage. Compilation verifies consistency, not predictive validity.
