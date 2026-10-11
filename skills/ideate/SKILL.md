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

Project Kit ships a launcher that works the same on macOS, Linux and Windows:

```bash
pk state -C . next          # read or write pipeline state
pk gate  -C . phase <name>  # may this phase run? exits non-zero if not
```

`-C <dir>` is the project directory; omit it to use the current one.

If `pk` is not on PATH, use the explicit form with whichever Python the machine has
(`python3`, `python`, or `py -3` on Windows):

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/pipeline/scripts/gate.py" -C . phase <name>
```

`pk gate phase <name>` checks the **environment** as well as pipeline state. Two outcomes
matter:

- **Exit 1** — report every reason verbatim and stop. Environment reasons carry their own
  `Fix:` command; pass it on rather than paraphrasing.
- **An `advisories` array in the output** — the phase may run, but something will break a
  later one. Tell the user now, in one line, rather than letting them discover it three
  phases in.

## Step 1: Gate

```bash
pk gate -C . phase ideate
```

Exit 1: report the reasons verbatim and stop. If it reports no `pipeline.json`, run
`/pipeline` first to create one — do not create it yourself.

```bash
pk state -C . phase ideate "in progress"
```

## Step 2: Understand the idea

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

## Step 3: Research prior art

Search for what already exists. This is the step people skip and regret.

For each close alternative, record what it does well and where it falls short *for this
job*. "It exists already" is not a reason to stop — "it exists already and does this job
adequately" is. Say which it is.

Mark every finding `VERIFIED` (you fetched it) or `ASSUMED` (you recall it). Do not present
recalled product details as verified; they go stale.

## Step 4: Write research.md

Write `docs/research.md` from `references/research-template.md`. Fill every section. Where
you have nothing, write "nothing found" rather than deleting the heading — an empty section
is information.

## Step 5: Precision check

Before claiming completion, list what the user asked for and map each item to a section you
actually wrote. If anything is unmapped, say so plainly and do not claim completion.

## Step 6: Record and hand off

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
