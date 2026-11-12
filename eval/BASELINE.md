# Filing baseline

**Not recorded yet.** The scorer and 150 builder-written captures are in place; the first
baseline run against the real model has not happened.

## What is missing

1. **An Anthropic API key where the scorer runs.** The cloud session that built slice 2 had
   none (Anthropic keys cannot be saved as a network secret there). Add `ANTHROPIC_API_KEY`
   as an environment variable in the cloud environment's settings and start a new session,
   or run it locally with the key exported.
2. **50 captures written by someone other than the builder** (`eval/WRITING_CAPTURES.md`).
   Without them the set is 150 of 200 and the baseline is the builder's own words only, which
   the spec warns overstate the real rate.

A baseline on the 150 builder cases is still worth recording as soon as there is a key:
it measures the prompt, and it is the number the other-people subset will be compared with.

## How to record it

```bash
pip install -r requirements.txt
python -m eval.score --limit 20        # smoke set first: under €0.01
python -m eval.score                   # the whole set; writes eval/report.json
```

Then fill in the table below from the printed summary and commit `eval/report.json` with it.

| Date | Model | Prompt | Cases (builder / others) | Fully correct: all | builder | others | Mean cost / capture |
|---|---|---|---|---|---|---|---|
| — | `claude-haiku-5-5` | `p1` | 150 / 0 | — | — | — | — |

Per kind (task, expense, trip, edit, budget, paste, note) is in the printed summary and in
`eval/report.json` under `summary`.

## What "fully correct" means

After the Validator (a rejected batch becomes a note) and its normalisation (unknown
category → Other), the filed ops and the expected ops are the same set of structured facts:
op kind, ref, amounts, dates and times, category and trip link (`dumpit_ops/compare.py`).
Titles, descriptions and trip names are not compared; for an update, which fields it sets
are compared, and the values of the structured ones. Any note matches an expected note.
