---
name: build
description: Build the project one backlog slice at a time, test-first: write the slice's acceptance scenarios as automated tests, implement until they pass, and let `pk slice done` decide when the slice is finished. Runs after /initiate. Use when the user says /build, "build the next slice", "build slice 3", "continue building", "implement the backlog", or when /pipeline or /initiate hands over to the build phase.
---

# /build

Turns `docs/backlog.md` into working, tested code, one slice at a time. Each slice ends
with its scenarios passing as automated tests and a commit. The pipeline's `build` phase is
complete when every slice is.

## Hard rules

1. **The script decides when a slice is done, not you.** `pk slice done <n>` refuses unless
   every scenario of the slice is named in a test and the project's test command exits 0.
   Never record a slice complete any other way, and never edit `pipeline.json` by hand.
2. **Test first.** Write the slice's scenarios as tests, run them and see them fail, then
   implement. A test that passed before any code was written proves nothing.
3. **Never weaken a test to get green.** No skipping, deleting, `xfail`, loosened asserts or
   mocking out the thing under test. If a scenario cannot pass as written, the spec is wrong:
   stop, record `pk slice block`, and tell the user.
4. **Stay inside the slice.** Build what its **Delivers** and **Touches** lines say, and
   nothing from later slices. Shared groundwork a later slice needs waits for that slice.
5. **Never invent secrets or results.** When a slice needs an API key, an account or a
   person (a hosted database, an email service, captures written by someone else), build
   everything that does not depend on it, then block the slice with the reason and ask.
6. **Record before handing off.** A slice that `pk slice done` did not accept is not done.

## Commands

Project Kit ships a launcher, `bin/pk`. **Resolve its path once, then use that literal path
in every later command** — each Bash call is a fresh shell, so no variable survives between
them, and `$CLAUDE_PLUGIN_ROOT` is *not* exported into the shell environment.

```bash
# If pk is already on PATH (setup.sh --fix puts it there), just use `pk` and skip this.
command -v pk || ls -d "$HOME"/.claude/plugins/cache/project-kit/project-kit/*/bin/pk \
                       "$HOME"/.claude/skills/project-kit/bin/pk 2>/dev/null | tail -1
```

Take the path it prints and substitute it wherever this skill says `pk` below. If it prints
nothing, Project Kit is not installed correctly — tell the user to run
`claude plugin install project-kit` and stop.

`-C <dir>` is the project directory; omit it to use the current one.

| Command | What it does |
|---|---|
| `pk gate -C . phase build` | may the build phase run here? (state + environment) |
| `pk slice -C . next` | the slice to build next, its scenarios, whether it may start |
| `pk slice -C . list` | every slice and its status |
| `pk slice -C . config --test-command "<cmd>" [--tests <dir>]` | how this project runs its tests |
| `pk slice -C . start <n>` | mark slice n in progress |
| `pk slice -C . check <n>` | dry run of `done`: lists what still stops it |
| `pk slice -C . done <n>` | runs the tests, checks the scenarios are mapped, records it |
| `pk slice -C . block <n> --reason "<why>"` | record why it cannot proceed |

Exit 1 from any of them means **refused**: report every reason verbatim and act on it.

## Step 1: Gate

```bash
pk gate -C . phase build
```

Exit 1: report verbatim and stop. A refusal naming `initiate` sends the user to `/initiate`.

## Step 2: Pick the slice

```bash
pk slice -C . next
```

Build the slice it names, unless the user named one (`/build 3`): then use that one.
If `test_command` is `null`, this is the project's first slice. Decide how the project
runs its tests from what is there (`pyproject.toml` → `python -m pytest -q`,
`package.json` → `npm test`, `go.mod` → `go test ./...`) or from the spec's stack, and
record it once:

```bash
pk slice -C . config --test-command "python -m pytest -q" --tests tests
```

## Step 3: Start and read

```bash
pk slice -C . start <n>
```

Read the slice in `docs/backlog.md` (Delivers, Scenarios, Touches, Done when), each of its
scenarios in `docs/acceptance.feature`, and the parts of `docs/spec.md` its Touches line
names: Interfaces, Data model, Failure modes, Security and privacy. Read the code earlier
slices left. Do not re-plan: the spec is approved.

## Step 4: Tests first

Write one automated test per scenario. **Put the scenario's exact name in the test**, in
its name, docstring or a comment — that is how `pk slice` maps scenarios to tests:

```python
def test_old_sign_in_link_is_refused():
    """Scenario: an old sign-in link does not sign anyone in"""
```

Test at the lowest level that proves the scenario (a pure function before an HTTP call,
an HTTP call before a browser). Stub only what the slice does not own: the model provider,
the clock, email delivery. Run the test command and **see the new tests fail**.

## Step 5: Implement

Write the code until the slice's tests pass, then run the whole suite: earlier slices must
still pass. Keep to the spec's names, interfaces and data model. A change the spec did not
foresee (a library, a field, an endpoint) is fine when the slice needs it; say so in the
report.

## Step 6: Check, then record

```bash
pk slice -C . check <n>
pk qa -C . lint
pk qa -C . backlog
```

Fix whatever `check` lists and run it again until it exits 0. If the slice changed UI files
also run `pk qa -C . a11y`. Then:

```bash
pk slice -C . done <n>
```

## Step 7: Commit

Commit the slice on the project's current branch (never `main` of someone else's repo
without being asked):

```bash
git add -A && git commit -m "Slice <n>: <name>"
```

Push only when the user asked for pushes.

## Step 8: Report, then continue or stop

    SLICE <n> DONE  <name>
    Scenarios:   <k> passing   (<test files>)
    Suite:       <passed> passed
    Built:       <one line per component>
    Waiting on:  <anything blocked on a key, an account or a person, or "nothing">
    Next:        Slice <m>: <name>   (<i> of <total> slices complete)

Then act on the mode (`pk slice -C . next` prints it):

| Mode | What you do |
|---|---|
| `manual` | Stop. The user starts the next slice. |
| `auto` | Stop after each slice and ask "Build slice <m>?" |
| `yolo` | Go straight to Step 2 for the next slice, until every slice is done, a slice is blocked, or the budget trips. |

When `done` reports `"build_complete": true`, the build phase is recorded complete; hand
back to `/pipeline` for what follows.

## When a slice is blocked

```bash
pk slice -C . block <n> --reason "needs ANTHROPIC_API_KEY to record the baseline"
```

Tell the user exactly what is needed and where it goes (an environment variable, an
account, a file), then move to the next slice that does not depend on it — or stop if none
can proceed.
