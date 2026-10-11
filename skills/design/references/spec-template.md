# Technical spec: <name>

> Phase 3 of the Project Kit pipeline. Bound by the v1 cut and out-of-scope list in
> docs/proposal.md. Acceptance criteria live in docs/acceptance.feature.

## Architecture

<One text diagram. Components and what each owns.>

| Component | Owns | Depends on |
|---|---|---|

## Decisions

Each decision names what lost and why. A decision with no rejected alternative was not one.

| Decision | Chosen | Rejected | Why |
|---|---|---|---|

**Reused from existing work:** <pattern and the file it came from, or "none — all new">

## Data model

| Entity | Fields | Lives in |
|---|---|---|

- **Schema versioning:** <how versions are tracked>
- **Migration:** <forward>; **reverse:** <backward, or state plainly that it is one-way>

## Interfaces

<The boundaries other code depends on. Signatures or endpoints.>

## Failure modes

| What goes wrong | System does | Scenario |
|---|---|---|
| <failure> | <behaviour> | <Gherkin scenario name> |

Every row needs a scenario in docs/acceptance.feature.

## Rollback

| Layer | How | Tested by |
|---|---|---|
| Code | <revert / redeploy a tag> | |
| Data | <reverse migration, or why none is needed> | |

An untested rollback is not a rollback.

## Security and privacy

| Concern | Handling |
|---|---|
| Sensitive data | |
| Secrets | |
| What gets logged | |

## Not built

<Explicitly out of scope, carried from the proposal so no reader assumes it was covered.>

## Strongest counter-argument

<The most plausible case that this design is wrong. Not a strawman. If you wrote the
design, argue against it harder, not softer. /handover carries this to the judges.>
