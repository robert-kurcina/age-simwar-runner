# Scenario generation guidance

The engine supports distinct personal investigation and institutional simulation frameworks. Generate proposals for review, not executable code. Treat scope, setting, authority, mechanics, presentation and objectives as separate design decisions.

## Generation contract

1. Establish fictional setting, provenance, scale, player role and intended gameplay length. Distinguish verified source facts from assumptions and fictional developments.
2. Select an existing supported framework. Identify participants and eligible player perspectives, objectives, resource constraints and information boundaries. Use one scenario definition for multiple perspectives.
3. Specify expected duration separately from the actual maximum turns, clock and terminal conditions. Use outcome dimensions and distinct conclusion types rather than assuming binary victory.
4. Describe scheduled and conditional events, dependencies, decision categories and permissible actions. Use existing engine-supported actions and effects only; never invent an executable mechanic by writing prose or arbitrary code.
5. Validate references and numeric bounds, test representative routes and failure cases, and obtain approval before treating generated configuration as playable. Freeze the approved rules before starting a session.
6. Display only actor-visible information. Preserve actual engine results. Do not reconstruct hidden state from a compressed player summary.

Generation is currently a design workflow, not an implemented automatic generator. Supported execution remains bounded fictional investigation and civilian/institutional simulation. No operational combat model or real-world targeting adjudication is implied.

## Strategic presentation

Use the staff-briefing profile in frameworks/strategic/presentation.json as a presentation preference, not a resolution rule. Report actual player results, other participant developments if available, assessment, then legal options. Show fewer options if only fewer are supported. Do not fabricate independent actor actions, effects or confidence estimates. Free-form requests must map to validated actions; unsupported requests do not execute. Optional statements are narrative unless the engine explicitly supports consequences.

Duration presets and challenge/fidelity/visibility labels in settings.json are design suggestions only. Do not claim a setting changes mechanics until the selected framework implements it.

### Supported dependent events

Strategic configurations may optionally contain `dependent_events`: one-shot events with a unique ID, due minute, existing participant ID, nonempty `requires` array of integer at-least conditions and nonempty `updates` mapping of integer deltas. Conditions and updated variables must be visible without reporting delay to that participant. A debit needs a sufficient same-key minimum guard. Authored fixed events occur first, then turn-boundary administrative reviews, then dependent events in authored order, then constraints. Unmet conditions cause a recorded skipped outcome, not a retry. Only the trusted scenario author specifies effects and participant authority; visibility is not an authorization model. No arbitrary expressions, automatic generated policies or recurring events yet. Player projections expose only their existing visible values and objectives, not the private background event ledger.
