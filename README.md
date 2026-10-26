# Project Kit

A Claude Code plugin that takes an idea from research to a launched product, with an
**independent cross-model judge gate** before development is allowed to start.

Twelve skills compose into one pipeline. Each skill reads shared state, refuses to run if
its preconditions are unmet, does its work, records what it produced, then hands off. Gates
are enforced by scripts — not by a model asserting that a gate passed.

- 🚶 **[Walkthrough](https://miricoder.github.io/project-kit/walkthrough.html)** — one idea carried the whole way, step by step
- 📖 **[Pipeline docs](https://miricoder.github.io/project-kit/)** — skill-by-skill detail, the flow, phase interaction
- 📊 **[Know-how and project tracker](https://miricoder.github.io/project-kit/project_kit_know_how.html)** — install guide and the status of every project you have run through it

> **Picking this up on another machine, in the cloud, or on a phone?** Start with
> [HANDOVER.md](HANDOVER.md) — state of play, decisions already taken, and the traps that
> have already cost time. [docs/roadmap.md](docs/roadmap.md) has what is built and what is next.

## Requirements

- **Claude Code 2.x or newer.** Plugin support is required — 0.x and 1.x builds have no
  `plugin` command at all. Check with `claude --version`.
- **Python 3.9+** (`python3`, `python`, or `py -3` on Windows). The gate and state logic is
  pure standard library.
- **Optional, for the judge gate only:** access to three different model families. The
  first three phases need none.

## Setup

Run the setup script first. It checks everything above, tells you exactly what is missing,
and prints the command to fix each item. It changes nothing unless you pass `--fix`.

**macOS / Linux**

```bash
git clone https://github.com/miricoder/project-kit
cd project-kit
./setup.sh
```

**Windows PowerShell**

```powershell
git clone https://github.com/miricoder/project-kit
cd project-kit
.\setup.ps1
```

> If PowerShell refuses to run the script, allow it for this session only:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`

Options (both platforms; PowerShell uses `-Fix` style, the shell uses `--fix`):

| Option | Does |
|---|---|
| *(none)* | Report only. Safe, changes nothing |
| `--fix` / `-Fix` | Apply the safe fixes, prompting for git identity if unset |
| `--dev` / `-Dev` | Development install — symlink this repo into `~/.claude/skills` so edits load live |
| `--live` / `-Live` | Also probe each judge seat with a tiny real call. **Configured is not the same as working** — a key can authenticate and still be out of credit |
| `--json` / `-Json` | Machine-readable report |

Exit code is `0` when every required check passes, `1` otherwise — so you can gate a script
on it.

### The environment check also runs automatically

You do not have to remember to run `setup.sh`. Every skill calls
`pk gate phase <name>` before doing anything, and that checks the **environment** as well
as pipeline state — **phase-aware**, so nothing pays for a check it does not need:

| Phase | Environment requirement | Behaviour if unmet |
|---|---|---|
| `/ideate`, `/proposal`, `/design` | none | runs; warns early if a later phase will break |
| `/handover`, `/verdict` | three working judge seats | **refuses**, naming the shortfall and the fix |
| `/initiate` onward | git identity set | **refuses**, with the `git config` command |

Results are cached for 24 hours at `~/.claude/project-kit/environment.json`, so the common
path costs nothing measurable. `pk doctor` refreshes the cache; `pk gate phase X --skip-env`
checks pipeline state only.

The point of the early warning: a judge panel short of a seat is discovered at `/ideate`,
not three phases later when `/handover` refuses.

## Install

```bash
claude plugin marketplace add miricoder/project-kit
claude plugin install project-kit
```

Then `/reload-plugins`, or start a new session. Verify with
`claude plugin details project-kit`; update later with `claude plugin update project-kit`.

## Quick start

```
/ideate an app that tracks my houseplants and tells me when to water them
```

That is it. `/ideate` sorts out where the project lives, sets up `pipeline.json`, then
researches the idea, frames the user and the job, surfaces the open questions, and hands
off down the pipeline.

**On directories.** The pipeline writes `pipeline.json` and `docs/` into the directory you
run it from, so it checks that the directory is a sensible home first:

| Where you run it | What happens |
|---|---|
| An empty directory | Used as-is; the project takes its name |
| An existing git repo | Used as-is — brownfield work is expected |
| A folder of unrelated work (`~/projects`) or your home directory | `/ideate` creates a subdirectory named from your idea and works there |
| Inside the Project Kit plugin | Refused — that would write your files into the tool's own source |

Pass `--here` to `pk state init` only if you deliberately want to initialise in place.

A bare `/ideate` with no idea asks what you want to build and writes nothing, leaving the
directory exactly as it found it.

## Using it from a terminal

The plugin works in any Claude Code session — the VS Code extension, or the CLI.

### macOS / Linux

```bash
cd ~/projects/my-idea          # the project directory; state lives here
claude                         # start an interactive session
```

Then inside the session:

```
/reload-plugins                # only needed the first time after installing
/pipeline                      # where am I, what runs next
/ideate <your idea>
```

For a scripted, non-interactive run:

```bash
claude -p "/ideate an app that tracks my houseplants"
```

### Windows PowerShell

Identical, with PowerShell path conventions:

```powershell
Set-Location $HOME\projects\my-idea
claude
```

```
/reload-plugins
/pipeline
/ideate <your idea>
```

PowerShell specifics worth knowing:

- **Execution policy** — `.ps1` files may be blocked. Allow for the session only:
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`
- **Python name** — Windows usually has `py -3` rather than `python3`. The `pk` launcher and
  `setup.ps1` detect this for you; only matters if you call the scripts directly.
- **Paths with spaces** — quote them: `.\setup.ps1` from inside the repo avoids the issue.
- **Claude Code on Windows** routes its shell tooling through Git Bash. If `/ideate` reports
  that a command was not found, install [Git for Windows](https://gitforwindows.org/) and
  re-run `.\setup.ps1`.

### The `pk` launcher

Skills call a small launcher rather than a hardcoded `python3`, which is what makes them
work identically across the three platforms:

```bash
pk state -C . next            # what phase am I in
pk gate  -C . phase design    # may /design run? non-zero if not
pk doctor --live              # re-run the environment check
pk keys status                # what the judge panel has and what it is missing
```

Explicit form, if `pk` is not on PATH:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/pipeline/scripts/gate.py" -C . phase design
```

## The pipeline

| Skill | Phase | Owns | Status |
|---|---|---|---|
| `/pipeline` | all | Phase state, gates, artifact registry, routing, resume, run mode | ✅ |
| `/ideate` | RND | Idea research, prior art, user and job framing, open questions | ✅ |
| `/proposal` | RND | Scope, v1 cut, explicit out-of-scope, cost estimate | ✅ |
| `/design` | Design | Full-stack design, technical spec, Gherkin acceptance criteria | ✅ |
| `/handover` | Handover | Builds the judge case and brief, runs the panel, validates verdicts | ✅ |
| `/verdict` | Approval | Reads the ruling, ranks fixes, back-propagates, admins rounds | ✅ |
| `/remediate` | Handover ↔ Approval | **The yolo loop.** `pk qa` + judge panel → fix → re-check → re-judge, unattended, until everything passes; then hands to `/initiate` | ✅ |
| `/initiate` | Initiation | **Judge-gated.** Asks before development starts; approved spec → feature backlog | ✅ |
| `/build` | Build | Implements one backlog slice: code plus unit tests | planned |
| `/devops` | DevOps | Repo, branches, PRs, releases, tags, CHANGELOG, CI, migrations | planned |
| `/test` | Testing | Pre-release gate: suite, coverage, acceptance-criteria verification | planned |
| `/security` | Security | Threat model, secret-in-history check, dependency audit | planned |
| `/launch` | Launch | Soft launch, rollback drill, hotfix path, observability | planned |

Three hard gates: the **judge gate** guards `/initiate`; the **test gate** and **security
gate** guard `/launch`.

## Run modes

Set once; stored in the project's `pipeline.json` and persists across sessions.

| Mode | Behaviour |
|---|---|
| `manual` | Stops after **every** skill and presents a menu of what can run next |
| `auto` *(default)* | Advances between phases, stopping at four checkpoints |
| `yolo` | Allow-all. End to end with no pipeline stops, subject to the budget cap |

The four `auto` checkpoints: after `/ideate` (is this the idea?), after `/proposal` (accept
scope and cost?), before the panel runs (this spends API credit), and after `/verdict`
(accept the ruling, or revise and re-judge?).

### Two layers of autonomy

`yolo` removes Project Kit's own checkpoints. It **cannot** remove Claude Code's tool
permission prompts — those are harness-level and no plugin can suppress them. For a
genuinely unattended run you also need an allowlist:

```jsonc
// ~/.claude/settings.json
{
  "permissions": {
    "allow": ["Bash(python3:*)", "Bash(git:*)", "Bash(gh:*)", "Edit", "Write"]
  }
}
```

`/pipeline mode yolo` reports whether this is configured, so the mode never *looks*
hands-off while silently waiting on a prompt.

### Budget cap

`yolo` adds no confirmation stops, but honours `budget.max_usd` in `pipeline.json`. On
exceeding it the run halts and reports. Set it as high as you like — what it rules out is an
unattended `REJECT` → re-judge → `REJECT` loop burning credit with nobody watching.

## Judge panel setup

The judge gate needs **three verdicts from three different model families**. Two rules are
enforced mechanically, not left to judgement:

1. **No family may hold two seats.** Two judges from one family share priors, producing a
   ruling that looks independent and is not.
2. **The authoring family is excluded.** Claude writes the plan, so Anthropic cannot judge
   it. An `ANTHROPIC_API_KEY` is reported as unusable rather than counted.

**A judging round needs at least one key.** Keys are never committed: this repository is
public, and a key in it is readable, and spendable, by anyone. Before `/design` and again at
`/handover` (in every mode, `yolo` included), Claude checks the panel and, if it is short,
**asks you** which provider's key you can give and how to fill the other seats. You store
the key yourself, in your own terminal, with input hidden:

```bash
pk keys add openai --live     # or google, moonshot, xai, deepseek, mistral
pk keys paste-rest            # fill the seats still empty with paste seats
pk keys status                # ready: true once three families sit
```

`pk keys` writes `~/.claude/project-kit/.env` with mode `600` in a `700` directory and never
prints the key. Don't type a key into the chat. In a cloud session, set the variable
(`OPENAI_API_KEY`, …) as a secret in the environment settings instead; `pk` reads it from the
process environment. Editing the file by hand still works:

```bash
mkdir -p ~/.claude/project-kit
cat > ~/.claude/project-kit/.env <<'ENV'
MOONSHOT_API_KEY=...
GEMINI_API_KEY=...
ENV
chmod 600 ~/.claude/project-kit/.env
```

Each seat uses the cheapest transport available:

| Transport | When |
|---|---|
| `api_key` | A real API key exists. Fully automated |
| `cli` | A subscription-backed CLI — e.g. `npm i -g @openai/codex` reuses an existing ChatGPT login, no API key and no extra cost |
| `paste` | Neither. The brief is rendered for you to paste, and the returned JSON is validated before being accepted |

No keys at all, and you want to paste all three judges by hand? Say so when asked, or name
the families yourself, and the panel can sit:

```bash
echo 'PROJECT_KIT_PASTE_SEATS=google,moonshot,openai' >> ~/.claude/project-kit/.env
```

Default models are overridable per family (`PROJECT_KIT_MODEL_OPENAI=<model>`), as are the
per-token prices the budget estimate uses (`PROJECT_KIT_PRICE_OPENAI=<in>,<out>` in USD per
million tokens).

> A ChatGPT subscription is **not** an OpenAI API key. Using `api_key` for that seat means
> paying for API usage separately; `cli` avoids it.

Verify with `./setup.sh --live`, which attempts one tiny generation per seat. A key that
authenticates can still be out of credit.

### Running to green without supervision: `/remediate`

`/remediate` sits between the spec and development. It runs `pk qa` (plan lint,
accessibility of every UI mockup, judge gate), fixes what fails, re-checks, sends the plan to
the judges, applies every open fix, and re-judges — with no checkpoints — until `pk qa` passes
completely. Then it hands over to `/initiate`, which **always** asks before development starts.

It stops early only for: the budget cap, the round limit (raised to 10 for the loop), a panel
that cannot sit unattended (paste seats need a person), the same failure three passes running,
or two `REJECT`s in a row. Every iteration is logged in `qa/remediation-log.md`.

The plugin also ships a **hook**: whenever Claude writes a UI mockup (`ui/**/*.html` or
`*.dc.html`) inside a Project Kit project, it is re-scanned for accessibility at once and any
failure is handed straight back to be fixed. The scan needs Node.js and Playwright; axe-core
is fetched on first use into `~/.claude/project-kit/a11y`.

| Command | Does |
|---|---|
| `pk qa` | every check; exit 0 only when all pass; writes `qa/report.json` |
| `pk qa lint` | spec sections, failure modes → scenarios, decisions, rollback, scenario outcomes |
| `pk qa a11y [files]` | axe-core WCAG 2.1 A/AA, visible focus on every tab stop, reflow at 320px |
| `pk qa backlog` | every acceptance scenario is in a backlog slice |
| `pk judge rounds [n]` | show or raise this project's judge round limit (max 10) |

### What the judges evaluate

Every judge receives the same generated brief, `judge/round-<n>/brief.md`: the rules, nine
criteria (job fit, scope, feasibility, failure modes, data and rollback, security and
privacy, testability, cost, and the design's own counter-argument), the reply format, and
the whole plan. Each reply is validated against the form before it counts, and the three
verdicts are combined by a fixed rule (the median by severity) into `docs/ruling.md`, which
shows every judge's rating on every criterion. The full form is in
[skills/handover/references/judge-form.md](skills/handover/references/judge-form.md).

| Command | Does |
|---|---|
| `pk judge case` | write this round's `case.json` and `brief.md` |
| `pk judge seats` | which three families sit, how each is reached, the estimated cost |
| `pk judge run` | call the API and CLI seats; list the paste seats |
| `pk judge accept --family F --file reply.txt` | validate a reply you pasted by hand |
| `pk judge status` | each seat's verdict, valid or not, and why |
| `pk judge combine` | three valid verdicts → `ruling.json` and `docs/ruling.md` |
| `pk judge record` | re-derive the ruling from the raw replies and record it; refuses a hand-edited ruling or a plan changed since judging |

## Manual setup

Everything `setup.sh` does, by hand, if you would rather not run a script.

1. **Python 3.9+** — `python3 --version`. Install from python.org if missing.
2. **Claude Code 2.x+** — `claude --version`. If it prints 0.x or 1.x, or
   `claude plugin list` prints generic help, it is too old:
   ```bash
   npm uninstall -g @anthropic-ai/claude-code     # remove the stale install first
   npm install -g @anthropic-ai/claude-code@latest
   hash -r && claude --version
   ```
3. **git identity** — needed for commits:
   ```bash
   git config --global user.name  "Your Name"
   git config --global user.email "you@example.com"
   ```
4. **Install the plugin** —
   `claude plugin marketplace add miricoder/project-kit && claude plugin install project-kit`.
   For development instead, symlink the repo:
   `ln -s "$PWD" ~/.claude/skills/project-kit`
5. **Judge credentials** — see [Judge panel setup](#judge-panel-setup). Optional; the first
   three phases need none.
6. **Unattended allowlist** — only if you want `yolo` to run without prompts. See
   [Two layers of autonomy](#two-layers-of-autonomy).

## Troubleshooting

**`zsh: command not found: claude`.** Find out whether it is missing or just unreachable:

```bash
ls -l ~/.local/bin/claude /usr/local/bin/claude /opt/homebrew/bin/claude 2>/dev/null
```

*A path is listed* — it is installed and your shell cannot see it. An already-open terminal
keeps the `PATH` it started with, so a profile edit never reaches it. Put it where every
shell looks (`/usr/local/bin` is on the default system `PATH`, no `sudo` needed):

```bash
ln -sf ~/.local/bin/claude /usr/local/bin/claude
hash -r && claude --version
```

*Nothing listed* — install it:

```bash
curl -fsSL https://claude.ai/install.sh | bash
hash -r && claude --version
```

**`claude plugin` prints generic help, or the version is below 2.0.** An old build with no
`plugin` command. Remove it first, or it keeps winning the `PATH` race:

```bash
which -a claude                                        # every copy on your PATH
npm uninstall -g @anthropic-ai/claude-code             # if it came from npm
rm -f /usr/local/bin/claude /opt/homebrew/bin/claude   # stale symlinks

curl -fsSL https://claude.ai/install.sh | bash
hash -r && claude --version && claude plugin list
```

**`Invalid API key · Please run /login`.** A build predating subscription login, so it
demands a key it should not need. **Do not supply an API key** — Claude Code uses your
subscription, and this is unrelated to the judge panel keys. Apply the upgrade above; if it
still asks, run `claude` then `/login` once.

**The installer produces no binary.** It downloads to `~/.claude/downloads` and can fail
quietly. If you have the VS Code extension, point a wrapper at the binary it already ships —
see [the walkthrough](https://miricoder.github.io/project-kit/walkthrough.html) for the exact
snippet.

**Two Claude Code installs fighting over PATH.** Common when an old global install sits
outside your current npm prefix — for example a Homebrew-path install while `npm config get
prefix` points at an NVM directory. A plain `npm i -g` lands in the prefix and may lose the
PATH race. Remove the old one first, then reinstall, then `hash -r`. `./setup.sh` detects
this specific case and names both paths.

**`/pipeline` is not found.** The plugin is not loaded. Run `/reload-plugins`, or start a
new session. Confirm with `claude plugin list`.

**Skills report "command not found" on Windows.** Claude Code routes shell tooling through
Git Bash. Install Git for Windows and re-run `.\setup.ps1`.

**The judge panel says 3/3 configured but a round fails.** Configured means a key is
present, not that it works. Run `./setup.sh --live` to probe each seat.

**This plugin only works in Claude Code.** It is not a GitHub Copilot extension and not a
VS Code extension — those products do not read Claude Code skills.

## Where your data lives

| What | Where |
|---|---|
| Per-project pipeline state and gates | `<project>/pipeline.json` |
| Human-readable project snapshot | `<project>/.github/projects/<name>.md` |
| Registry of all projects, for the tracker page | `~/.claude/project-kit/registry.json` |
| Judge credentials | `~/.claude/project-kit/.env` (mode 600) |

Project data and credentials are deliberately **not** stored in this repo. This repo is the
tool.

## Development

```bash
git clone https://github.com/miricoder/project-kit
cd project-kit
./setup.sh --dev     # symlink into ~/.claude/skills so edits load live
pk check             # everything CI runs, same order
```

### Verifying a change before you push

`pk check` runs exactly what CI runs, so you find problems locally instead of after a push:

```
Project Kit — repository checks (same as CI)
============================================

[ ok ]  Unit tests        Ran 139 tests in 0.990s
[ ok ]  Docs up to date   generated pages match their sources
[ ok ]  Plugin manifests  validate --strict passed

All required checks passed.
Safe to commit and push.
```

| | |
|---|---|
| `pk check` | Unit tests → docs freshness → manifest validation |
| `pk check --fix` | Regenerate stale docs rather than only reporting them |
| Exit code | `0` all required passed, `1` otherwise — usable as a git hook |

A missing Claude Code CLI downgrades the manifest step to a warning rather than failing the
run, so the command still works on a bare machine. A test pins these steps against
`.github/workflows/ci.yml`, so the two cannot quietly drift apart.

Release: bump `version` in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`,
then `claude plugin tag --push` — it refuses unless both agree.

## Licence

MIT
