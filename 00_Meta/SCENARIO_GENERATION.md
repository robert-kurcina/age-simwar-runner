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

### Collective faction context (optional)

Private scenario compiler specs may include `faction_profiles` keyed by existing actor ID. Reuse participant profile syntax, kind organization, same label and effective date. Include only relevant qualitative context or dated native properties. The compiled opening profile is frozen into actor metadata and visible only to that actor; it is not a second mutable resource store. Actual quantities used by rules remain in existing initial/state variables. Profile references must use the existing source compiler; no individual agents, new universal attributes or corpus expansion. Omit the profile when existing objective and reviewed context suffice. Treat all included profile properties as safe for that actor to know. Existing Fiji pilot already has a dated relief objective and finite aid resources; no additional national metrics required for this scale. No private source content is copied into the public bundle.

### SH44SER Economy Design (bounded project slice)

Optional `economy_projects` records use an existing participant, Project Need 1–5, one to three ordered native capacity axes bound to existing 0–5 integer state keys, a positive stage count, and distinct progress/delay/complication counters. At each Turn boundary after reviews and dependent events, evaluate largest Shortfall; authored order breaks ties. Clear advances one stage; 1 loses a project Turn and records a Delay; 2 records Delay plus an abstract Complication; 3 stalls; 4+ requires rescoping. Delay here counts lost project Turns, not extra global time. Reassess next Turn; completed projects stop. Dated unconditional events may update capacity within 0–5. No arbitrary capacity inference, character Tests, cost substitution, resource spending, or mixed civic fulfillment yet. Project results are actor-local; all updates replay. The delay-only policy and generic Complication counter are AGE's bounded adaptation of native referee choices, not a full port. Use actual Economy Turn durations (e.g. weeks) for projects. The private scenario adapter remains restricted to its previously reviewed mechanics until the SH44SER vertical slice is integrated.

Capacity decisions: optional `capacity_actions` map existing action IDs to a project, a project-local capacity key, a resource stock key and positive integer cost. The sponsor alone may request the action. At review, spend the authored cost and raise capacity by one (maximum 5), only if the project is incomplete and resources suffice. Effects are fixed by scenario authors, never proposed by the model. Capacity/stock keys cannot receive competing scheduled updates in this slice. No new faction attributes or decision subsystem. The private adapter remains restricted pending the reviewed recovery scenario.
