---
name: launch
description: Go live. Deploys the tagged release to production on the user's own account, smoke-checks it, then rehearses a rollback against the real production service (roll back to the previous version, check it, restore the release, check it again). `pk ship done launch` records the launch only after all of that, with the test and security gates passed. Use when the user says /launch, "go live", "ship it", "deploy to production", "rollback drill", or when /pipeline hands over to the launch phase.
---

# /launch

The last phase. It is complete when `pk ship done launch` confirms all of these:

- the security gate and the test gate passed;
- production runs the release tag, over https, and answers its health check now;
- a rollback was rehearsed on production after that deploy: rolled back to a different
  version and checked, then restored to the release and checked.

A launch whose rollback has never been tried has no rollback.

## Hard rules

1. **Production only through the gate.** `pk ship record production` refuses until the
   security gate has passed and the version was on staging first. Never work around it by
   deploying without recording.
2. **Ask before the first production deploy**, in every mode, including yolo. Going live
   reaches real users and real money. Say what will be deployed, where, and which settings
   it uses, then wait for a yes.
3. **Secrets as at `/devops`.** Production has its own database and keys. Never reuse
   staging data, and never echo a value.
4. **The rollback drill is real.** It changes which version production serves, so do it
   right after the first deploy, before users arrive, and tell the user when it runs.

## Commands

Project Kit ships a launcher, `bin/pk`. Resolve its path once, then use that literal path
in every later command (each Bash call is a fresh shell):

```bash
command -v pk || ls -d "$HOME"/.claude/plugins/cache/project-kit/project-kit/*/bin/pk \
                       "$HOME"/.claude/skills/project-kit/bin/pk 2>/dev/null | tail -1
```

| Command | What it does |
|---|---|
| `pk gate -C . phase launch` | may launch run? (security gate passed, all phases before it complete) |
| `pk ship -C . record production --url <url> --version <tag>` | smoke-check, then record the production deploy |
| `pk ship -C . record production --url <url> --version <prev> --kind rollback` | record the rolled-back state |
| `pk ship -C . record production --url <url> --version <tag> --kind restore` | record the restored release |
| `pk ship -C . done launch` | check everything and record the launch |

## Step 1: Gate

`pk gate -C . phase launch`. On exit 1, report it verbatim and stop. A refusal naming the
security gate sends the user to `/security`.

## Step 2: Production settings

`pk ship -C . status` lists the setting names from `/devops`. Ask the user for the
production values. They are separate accounts and databases from staging. The values go
into the platform's secret store, as in `/devops` Step 4.

## Step 3: Deploy (after asking)

Ask (rule 2). Then deploy the release tag with the production recipe from
`skills/devops/references/targets.md` (the service without `-staging`), and run:

```bash
pk ship -C . record production --url https://<prod url> --version <tag>
```

## Step 4: Rollback drill

There must be a version to roll back to. On a first launch there is no earlier production
revision, so deploy the previous release (or the previous staging commit) first. Then
deploy the release, which gives two revisions. Then:

1. Roll production back to the previous version (the target's **Rollback** command), and
   `pk ship -C . record production --url <url> --version <previous> --kind rollback`.
2. Restore the release (the target's **Restore** command), and
   `pk ship -C . record production --url <url> --version <tag> --kind restore`.

Write down in `docs/runbook.md` how long each step took and the exact commands. That page is
what someone follows when a bad release reaches production: how to roll back, where the
logs are, and who holds the accounts.

## Step 5: Record the launch

```bash
pk ship -C . done launch
```

## Step 6: Report

    LAUNCHED  <project> <tag>
    Production:  <url>   (health answered <status> in <ms> ms)
    Rollback:    rehearsed: <tag> → <previous> → <tag>, both checked
    Runbook:     docs/runbook.md
    Open it:     on a phone, open <url> in Safari or Chrome, then Add to Home Screen

The pipeline is complete.
