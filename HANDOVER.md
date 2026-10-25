# Handover

Everything a fresh session — on another machine, in the cloud, or on a phone — needs to
pick this up. Chat transcripts are local to the machine that made them and cannot be
moved, so this file is the substitute: state of play, decisions already taken, and the
traps that have already cost time.

Keep it current. It is the first thing to read and the first thing to update.

## What Project Kit is

A Claude Code plugin taking an idea from research to a launched product, with an
independent cross-model judge gate before development may start. Gates are enforced by
Python scripts with exit codes — never by a model asserting a gate passed. That is the
whole design premise.

## State of play

| | |
|---|---|
| Version | see `.claude-plugin/plugin.json` |
| Skills built | `/pipeline`, `/ideate`, `/proposal`, `/design` — idea → technical spec |
| Skills remaining | 8, see [docs/roadmap.md](docs/roadmap.md) |
| Tests | `pk check` runs exactly what CI runs |
| Docs | <https://miricoder.github.io/project-kit/> — generated, never hand-edited |

**What works today:** idea → researched brief → scoped proposal → technical spec with
Gherkin acceptance criteria. No credentials needed for any of it.

**What does not:** the judge gate and everything after. `/handover` and `/verdict` are the
next thing to build.

## Decisions already made — do not relitigate without reason

1. **Gates are mechanical.** A gate passes only on a recorded ruling that a script checked.
   If you find yourself writing "the model should check that…", stop.
2. **Anthropic cannot hold a judge seat.** Claude authors the plan; a Claude judge shares
   its priors. Enforced in code, not convention.
3. **Three distinct model families on the panel.** Seating one family twice produces a
   ruling that looks independent and is not.
4. **Tier is `standard`, not `high`, for greenfield plans.** At `high`, `combine.py`
   silently downgrades a unanimous `FIX FIRST` to `NEEDS INFO` when findings are
   `SPECULATING` — which they necessarily are when nothing is runnable yet.
5. **Shell wrappers stay thin.** `setup.sh` and `setup.ps1` only locate Python and hand off
   to `scripts/doctor.py`. Two shell implementations would drift.
6. **Docs are generated.** Edit `docs/build_docs.py`, never the HTML. CI fails on stale output.

## Traps that have already cost time

- **`$CLAUDE_PLUGIN_ROOT` is not exported into the shell.** Skills must resolve the
  launcher by path. A test now fails the build if any skill dereferences it in a command.
- **A version that does not move delivers nothing.** `claude plugin update` reports
  "already at the latest version" and ships no fixes. Bump both manifests every release.
- **An open terminal keeps its old `PATH`.** Editing a shell profile does not reach it.
  `/usr/local/bin` is on the default system PATH and writable without `sudo`.
- **Check the install a user actually gets**, not your working copy. A marketplace install
  silently took precedence over the development symlink and was several fixes behind.
- **`collect()` shells out to the test runner.** Any test calling it must stub the
  subprocess or the suite recurses into itself.

## Resuming anywhere

```bash
git clone https://github.com/miricoder/project-kit && cd project-kit
./setup.sh                 # or .\setup.ps1 — reports what is missing, changes nothing
pk check                   # exactly what CI runs
```

To use the plugin rather than develop it:

```bash
claude plugin marketplace add miricoder/project-kit
claude plugin install project-kit
```

### In a cloud session or on a phone

The repository is public, so the two install commands work anywhere with no credentials.
Two things do **not** travel:

- **Judge panel keys** live in `~/.claude/project-kit/.env` (mode 600) on one machine. Any
  environment running `/handover` needs its own copy. Never commit them.
- **Per-project pipeline state** (`pipeline.json`, `docs/`) lives in the working directory.
  A cloud workspace is disposable, so **make each product its own git repo** and push it, or
  the pipeline forgets the project when the session ends.

## Working agreement

- Every change lands on a branch and merges by PR, with CI green **before** merging.
- `pk check` before pushing.
- Bump the version on anything users should receive.
- When a tester reports a problem, reproduce it first and re-run the scenario *after*
  fixing — a guard added in one PR turned out to be unreachable, and only re-running the
  original report caught it.
