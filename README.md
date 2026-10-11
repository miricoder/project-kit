# Project Kit

A Claude Code plugin that takes an idea from research to a launched product, with an
**independent cross-model judge gate** before development is allowed to start.

Twelve skills compose into one pipeline. Each skill reads shared state, refuses to run if
its preconditions are unmet, does its work, records what it produced, then hands off. Gates
are enforced by scripts — not by a model asserting that a gate passed.

- 📖 **[Pipeline docs](https://miricoder.github.io/project-kit/)** — skill-by-skill detail, the flow, phase interaction
- 📊 **[Know-how and project tracker](https://miricoder.github.io/project-kit/project_kit_know_how.html)** — install guide and the status of every project you have run through it

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
| `/handover` | Handover | Builds the judge case and brief, runs the panel, validates verdicts | planned |
| `/verdict` | Approval | Reads the ruling, ranks fixes, back-propagates, admins rounds | planned |
| `/initiate` | Initiation | **Judge-gated.** Approved spec → feature backlog | planned |
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

Put credentials in `~/.claude/project-kit/.env`, mode `600`, never in the repo:

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

> A ChatGPT subscription is **not** an OpenAI API key. Using `api_key` for that seat means
> paying for API usage separately; `cli` avoids it.

Verify with `./setup.sh --live`, which attempts one tiny generation per seat. A key that
authenticates can still be out of credit.

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

**`claude plugin` prints generic help instead of plugin output.** Your CLI predates plugin
support. Follow step 2 of manual setup.

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
./setup.sh --dev                              # symlink into ~/.claude/skills
python3 -m unittest discover -s tests -t . -v
claude plugin validate . --strict
python3 docs/build_docs.py                    # regenerate the docs pages
```

Release: bump `version` in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`,
then `claude plugin tag --push` — it refuses unless both agree.

## Licence

MIT
