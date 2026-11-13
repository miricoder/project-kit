---
name: security
description: The security gate before launch. Writes docs/threat-model.md from the spec and the code, then `pk ship audit` scans every tracked file and every commit in history for secrets, audits the dependencies (pip-audit, npm audit), checks the threat model is complete, and records the security gate as PASS or FAIL in docs/security-audit.md. Runs after /test; /launch cannot start until it passes. Use when the user says /security, "security audit", "threat model", "check for leaked secrets", or when /pipeline hands over to the security phase.
---

# /security

`/launch` is gated on this. It passes only when `pk ship audit` finds all three of these:

- **no secrets** in the tracked files or anywhere in git history (keys, tokens, private
  keys, passwords in URLs);
- **no high or critical findings** from an audit of every dependency manifest;
- **a complete threat model**: `docs/threat-model.md` with Assets, Threats and Mitigations
  sections, and no TODO or TBD left in it.

For a deeper review of the code itself, Claude Code's built-in `/security-review` works
well alongside this. Fold what it finds into the threat model and fix it before the audit.

## Hard rules

1. **`pk ship audit` is the only way the gate passes.** Never record a ruling by hand.
2. **A leaked secret is revoked, not hidden.** Deleting it from the file does not help,
   because it stays in history. Tell the user to revoke and reissue the key at its
   provider first. Only then rewrite history, and only with the user's explicit
   permission, since rewriting history changes every clone. Never print the secret's value.
3. **Never suppress a dependency finding to pass.** Upgrade the package. If no fixed
   version exists, record the risk and its mitigation in the threat model and tell the
   user. The gate stays red until the audit is clean.
4. **A missing auditor is a failure, not a pass.** Install it (`pip install pip-audit`;
   npm ships `npm audit`).

## Commands

Project Kit ships a launcher, `bin/pk`. Resolve its path once, then use that literal path
in every later command (each Bash call is a fresh shell):

```bash
command -v pk || ls -d "$HOME"/.claude/plugins/cache/project-kit/project-kit/*/bin/pk \
                       "$HOME"/.claude/skills/project-kit/bin/pk 2>/dev/null | tail -1
```

| Command | What it does |
|---|---|
| `pk gate -C . phase security` | may the security phase run? (test must be complete) |
| `pk ship -C . audit` | run the gate, write `docs/security-audit.md`, record PASS or FAIL |

## Step 1: Gate

`pk gate -C . phase security`. On exit 1, report it verbatim and stop.

## Step 2: Threat model

Write `docs/threat-model.md` from the spec's **Security and privacy** and **Failure modes**
sections and from the code as it is now:

```markdown
# Threat model: <project>

## Assets
What an attacker would want: user data, sessions, API keys, money, the ability to send mail.

## Threats
One per line, specific to this system: who, which entry point, what they get.
E.g. "A stolen sign-in link is used by someone else within its 15-minute life."

## Mitigations
For each threat: what in the code stops it, with the file. Name the test that proves it
where one exists. A threat with no mitigation is a bug: fix it, or state the accepted risk
and why.
```

Check the code against each mitigation as you write it; do not copy the spec's intent. A
mitigation the code does not have goes in as a bug and gets fixed now.

## Step 3: Audit

```bash
pk ship -C . audit
```

On FAIL, act on each reason (rules 2 to 4), commit, and run it again. In `yolo` mode, loop
until it passes, unless a reason needs the user (a key to revoke, an accepted risk). Then
stop and ask.

## Step 4: Report

    SECURITY GATE PASS  at <commit>
    Secrets:       none in files or history
    Dependencies:  <manifests> clean
    Threat model:  <n> threats, each mitigated
    Next: /launch

Commit `docs/threat-model.md` and `docs/security-audit.md`.
