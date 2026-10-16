---
name: ideate
description: Research and frame a raw product idea — prior art, the user and the job, how it would work, what is uncertain — and write it up as research.md. The first phase of the Project Kit pipeline. Use when the user says /ideate, "I have an app idea", "I want to build something that...", "research this idea", or describes a product they are thinking about building.
---

# /ideate

Turn a raw idea into a researched brief that the rest of the pipeline can act on. You are
not deciding whether to build it, and you are not designing it. You are establishing what
it is, who it is for, what already exists, and what nobody yet knows.

## Hard rules

1. **Do not design.** No architecture, no stack, no schema. That is `/design`, two phases
   away. Naming a technology here anchors every later decision before the case for it exists.
2. **Separate what you verified from what you assumed.** Every claim about prior art, market
   or feasibility is marked `VERIFIED` (you looked it up this session) or `ASSUMED`.
3. **Open questions are a deliverable, not a failure.** The questions you surface here are
   what stop the judges returning `NEEDS INFO` three phases later.

## Commands

Project Kit ships a launcher, `bin/pk`. **Resolve its path once, then use that literal path
in every later command** — each Bash call is a fresh shell, so no variable survives between
them, and `$CLAUDE_PLUGIN_ROOT` is *not* exported into the shell environment.

```bash
# If pk is already on PATH (setup.sh --fix puts it there), just use `pk` and skip this.
command -v pk || ls -d "$HOME"/.claude/plugins/cache/project-kit/project-kit/*/bin/pk \
                       "$HOME"/.claude/skills/project-kit/bin/pk 2>/dev/null | tail -1
```

Take the path it prints and substitute it wherever this skill says `pk` below, for example:

```bash
/Users/you/.claude/plugins/cache/project-kit/project-kit/0.3.1/bin/pk gate -C . phase ideate
```

If it prints nothing, Project Kit is not installed correctly — tell the user to run
`claude plugin install project-kit` and stop.

`-C <dir>` is the project directory; omit it to use the current one.



The gate command checks the **environment** as well as pipeline state. Two outcomes
matter:

- **Exit 1** — report every reason verbatim and stop. Environment reasons carry their own
  `Fix:` command; pass it on rather than paraphrasing.
- **An `advisories` array in the output** — the phase may run, but something will break a
  later one. Tell the user now, in one line, rather than letting them discover it three
  phases in.

## Step 1: The idea, before anything is written

**If the user did not describe an idea, ask for it and stop.** One sentence is enough
("an app that ..."). Do not create files, do not initialise state: a bare `/ideate`
must leave the directory exactly as it found it.

## Step 2: Check the directory, then set up state

```bash
pk gate -C . phase ideate
```

Three outcomes:

- **Refused because this is inside the Project Kit plugin.** Say so and stop. The user
  needs an empty directory for their product; offer to continue once they move there.
- **`no pipeline.json`.** This is a new project — **set it up yourself**, do not make the
  user do it:

  ```bash
  pk state -C . init
  ```

  The project name defaults to the directory name.

  If that refuses because the directory is a poor home — the home directory, or a folder
  of unrelated work like `~/projects` — **do not pass `--here` to get around it.** Propose
  a subdirectory named from the idea and create it:

  ```bash
  mkdir -p houseplant-tracker && cd houseplant-tracker
  pk state -C . init
  ```

  Say which directory you created and that everything will live there. The shell keeps
  that working directory for the rest of the session, so later phases need no `-C`.
  Reserve `--here` for a user who explicitly asks to initialise in place.

- **Exit 1 for any other reason.** Report the reasons verbatim and stop.

Then:

```bash
pk state -C . phase ideate "in progress"
```

## Step 3: Understand the idea

If the user gave only a sentence, ask for what you cannot reasonably infer — but ask
**once**, in a single batch, and no more than five questions. Prefer inferring and marking
`ASSUMED` over interrogating. The judges will test your assumptions later; that is the
system working.

What must end up known:

- **The job.** What is the user trying to get done, in their words, not in features.
- **Who.** A specific person in a specific situation, not "users".
- **Today's workaround.** What they do now instead. If there is no workaround, question
  whether the job is real.
- **Platform reality.** Where it has to run, and whether it must work offline.
- **Data.** What is stored, how sensitive it is, where it lives.
- **The one thing** that, if it did not work, would make the whole thing pointless.

## Step 4: Research prior art

Search for what already exists. This is the step people skip and regret.

For each close alternative, record what it does well and where it falls short *for this
job*. "It exists already" is not a reason to stop — "it exists already and does this job
adequately" is. Say which it is.

Mark every finding `VERIFIED` (you fetched it) or `ASSUMED` (you recall it). Do not present
recalled product details as verified; they go stale.

## Step 5: Write research.md

Write `docs/research.md` from `references/research-template.md`. Fill every section. Where
you have nothing, write "nothing found" rather than deleting the heading — an empty section
is information.

## Step 6: Precision check

Before claiming completion, list what the user asked for and map each item to a section you
actually wrote. If anything is unmapped, say so plainly and do not claim completion.

## Step 7: Record and hand off

```bash
pk state -C . phase ideate complete --artifact docs/research.md
pk state -C . next
```

Report to the user:

    IDEATE  <idea name>
    Job:      <the job, one line>
    For:      <who>
    Prior art: <n> alternatives found — <closest one> is nearest
    Open questions: <n>
    Written: docs/research.md

Then follow the mode in `next`:

- **`manual`** — stop. Offer `/proposal` as the next step and wait.
- **`auto`** — `ideate` is a checkpoint. Show the summary, ask the user to confirm you
  understood the idea, and **wait**. Do not continue unprompted.
- **`yolo`** — invoke `proposal` via the Skill tool immediately.
