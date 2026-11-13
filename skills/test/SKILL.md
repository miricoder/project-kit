---
name: test
description: The pre-release test gate. Runs the full suite and checks that every acceptance scenario in docs/acceptance.feature is named in a test, then records the test gate as PASS or FAIL and writes docs/test-report.md. `pk ship test` decides, never the model. Runs after /devops. Use when the user says /test, "run the test gate", "is it ready to release", "check the acceptance criteria", or when /pipeline hands over to the test phase.
---

# /test

At /build each slice proved its own scenarios. This gate proves all of them together, on the
code that will ship. It passes only when **every** scenario in `docs/acceptance.feature` is
named in a test **and** the project's test command exits 0. It runs both checks itself.

## Hard rules

1. **`pk ship test` is the only way the gate passes.** Never record a ruling by hand, and
   never edit `pipeline.json`.
2. **Never weaken a test to get green.** No skipping, deleting, `xfail`, loosened asserts or
   mocking out the thing under test. A failing scenario is a bug in the code, or else a
   wrong spec. If it is the spec, stop and tell the user.
3. **Never rename a scenario so it maps.** If a scenario has no test, write the test.

## Commands

Project Kit ships a launcher, `bin/pk`. Resolve its path once, then use that literal path
in every later command (each Bash call is a fresh shell):

```bash
command -v pk || ls -d "$HOME"/.claude/plugins/cache/project-kit/project-kit/*/bin/pk \
                       "$HOME"/.claude/skills/project-kit/bin/pk 2>/dev/null | tail -1
```

| Command | What it does |
|---|---|
| `pk gate -C . phase test` | may the test phase run? (devops must be complete) |
| `pk ship -C . test` | run the gate, write `docs/test-report.md`, record PASS or FAIL |

## Steps

1. `pk gate -C . phase test`. On exit 1, report it verbatim and stop.
2. `pk ship -C . test`.
3. **PASS:** commit `docs/test-report.md` and report:

       TEST GATE PASS  <k> of <k> scenarios mapped, suite green at <commit>
       Next: /security

4. **FAIL:** read the reasons and `docs/test-report.md`, then:
   - for an unmapped scenario, write its test (the scenario's exact name goes in it, as at `/build`);
   - for a failing suite, find the cause and fix the code.

   Commit the fix, redeploy staging and record it (`/devops` Step 5), then run
   `pk ship -C . test` again. A code change after the release tag means a new release:
   bump the version, add a CHANGELOG entry, and run `pk ship release` again.

In `manual` and `auto` modes, stop after the report. In `yolo` mode, fix and re-run until
the gate passes. Then go to `/security`. The budget still halts the run.
