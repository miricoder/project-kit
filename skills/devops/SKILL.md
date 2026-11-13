---
name: devops
description: Make the project shippable. Adds CI that runs the tests, deploys to a staging environment on the user's own hosting account, smoke-checks it, writes the CHANGELOG and tags a release. `pk ship` records each step and decides when the phase is complete. Runs after /build. A staging deploy may be done earlier, while slices are still being built. Use when the user says /devops, "set up CI", "deploy to staging", "put it online", "cut a release", "tag a release", or when /pipeline hands over to the devops phase.
---

# /devops

Takes a built project to a tagged release that runs on staging. The phase ends when three
things are true, and `pk ship done devops` checks every one:

1. CI runs the project's test command (`.github/workflows/*.yml` or equivalent).
2. CI deploys to staging after the tests pass, so every iteration ships by itself.
3. Dependency updates are configured (`.github/dependabot.yml` or Renovate).
4. A release is tagged (`pk ship release v1.0.0`), with a CHANGELOG entry.
5. That release runs on staging and answers its health check, as recorded by `pk ship record`.

## Hard rules

1. **The script records; you never assert.** A deploy is recorded only by `pk ship record`,
   which smoke-checks the URL itself. A URL that does not answer is not deployed.
2. **Never invent or echo secrets.** The user's own accounts (hosting, database, email, API
   keys) are needed. Ask for them by name. Values go into the hosting platform's secret
   store or the user's shell, never into the repo, a commit, `pipeline.json` or the chat.
   `pk ship config --env` takes names only and refuses values.
3. **Never deploy to production here.** Production is `/launch`, after the test and
   security gates.
4. **Never push to `main`, force-push or delete a tag without being asked.** Releases are
   tagged on the project's current branch; pushing the tag is the user's call.
5. **Never skip or weaken CI to get green.** A red CI is a bug to fix, the same as at /build.

## Commands

Project Kit ships a launcher, `bin/pk`. **Resolve its path once, then use that literal path
in every later command.** Each Bash call is a fresh shell, so no variable survives between
them, and `$CLAUDE_PLUGIN_ROOT` is *not* exported into the shell environment.

```bash
# If pk is already on PATH (setup.sh --fix puts it there), just use `pk` and skip this.
command -v pk || ls -d "$HOME"/.claude/plugins/cache/project-kit/project-kit/*/bin/pk \
                       "$HOME"/.claude/skills/project-kit/bin/pk 2>/dev/null | tail -1
```

| Command | What it does |
|---|---|
| `pk gate -C . phase devops` | may the devops phase run here? (build must be complete) |
| `pk ship -C . status` | target, deploys, release, gates, phase states |
| `pk ship -C . config --target <t> --health <path> --env <NAME> ...` | record where and how it deploys |
| `pk ship -C . smoke <url>` | does the deployment answer its health path? |
| `pk ship -C . record staging --url <url>` | smoke-check, then record a staging deploy of HEAD |
| `pk ship -C . release v1.0.0` | tag HEAD as a release (refuses unless it is ready) |
| `pk ship -C . done devops` | check CI, release and staging, and record the phase |

Exit 1 means **refused**: report every reason verbatim and act on it.

## Step 1: Gate

```bash
pk gate -C . phase devops
```

If it refuses because `build` is not complete, you may still set up CI and staging
(Steps 2 to 5). Staging is how the user sees the work in progress on their phone and their
computer. Do not tag a release or run `done` until the build is complete.

## Step 2: Choose the target and record it

Read `docs/spec.md` (Architecture, Rollback, Security and privacy) for where it is meant to
run. Use what the spec says, and do not re-decide it. Then read
`references/targets.md` for that target's commands, and record:

```bash
pk ship -C . config --target cloudrun --health /v1/health \
  --env DATABASE_URL --env ANTHROPIC_API_KEY --env SMTP_URL --service <name>
```

`--env` lists every setting the running service reads that holds a secret or an account
(names only). These are what the user must supply.

## Step 3: CI

Write the CI workflow if there is none. It must run **exactly** the project's test command
(`pk slice -C . list` shows it as `test_command`), and set up whatever that command needs:
the language runtimes, a database service, browsers for end-to-end tests. Run on pull
requests and on pushes to the main branch. Never put a secret into the file; use the CI
provider's secret store, and keep the tests themselves free of real keys.

## Step 3b: Continuous deploy and dependency updates

Add the staging and production deploy jobs, following `references/targets.md` →
**Continuous deploy**. Gate them on repository variables, so they are skipped until the user
has set the target up. Write one `scripts/deploy.sh <env>` that both CI and a person run,
and stamp each build with its version. Add `.github/dependabot.yml` for every package
ecosystem in the repo. Write the one-time setup as a script the user runs in their own
account, in Cloud Shell or their terminal; it prints the variables they add to GitHub.

## Step 4: Ask for the accounts

List what the deploy needs that you do not have, in one message, then stop and wait:

    To deploy to staging I need:
      - A Google Cloud project with billing on (project id), and `gcloud auth login` done
      - DATABASE_URL: a Postgres database (Neon free tier, region eu-central-1)
      - ANTHROPIC_API_KEY: from console.anthropic.com
      - SMTP_URL: an email-sending account for sign-in links

    Put each value in the hosting platform's secret store (I will give you the command),
    or export it in your shell. Do not paste it here.

If the session cannot reach the hosting CLI or the user's account (a cloud sandbox with no
credentials), say so plainly. Hand the user the exact commands from
`references/targets.md` to run on their own computer, then record the result here with
`pk ship record` once the URL answers.

## Step 5: Deploy to staging and record it

Run the target's deploy command from `references/targets.md`, then:

```bash
pk ship -C . record staging --url https://<the staging url>
```

A refusal means the service is not answering its health path. Read the platform's logs
(`references/targets.md` has the command), fix the cause, deploy again and record again.

## Step 6: CHANGELOG and release

When the build is complete and the CI is green, write a `CHANGELOG.md` entry for the
version (Keep a Changelog style: Added, Changed, Fixed). Draw it from the backlog's slices
and the commits. Commit it, deploy that commit to staging and record it, then run:

```bash
pk ship -C . release v1.0.0
```

It refuses unless the working tree is clean, the CHANGELOG names the version, and HEAD is
recorded on staging. Tell the user how to push the tag (`git push origin v1.0.0`). Push it
only if they asked for pushes.

## Step 7: Record the phase

```bash
pk ship -C . done devops
```

## Step 8: Report

    DEVOPS DONE  <project>
    CI:         <workflow file>, runs `<test command>`
    Staging:    <url>   (health <path> answered <status> in <ms> ms)
    Release:    <tag> at <commit>
    Needs:      <settings the user still has to supply for production, or "nothing">
    Next:       /test

In `manual` and `auto` modes, stop here. In `yolo`, go on to `/test`.
