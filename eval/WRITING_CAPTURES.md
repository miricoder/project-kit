# Writing captures for the filing test set

The test set needs **at least 50 captures written by someone other than the builder**
(docs/backlog.md, slice 2; the spec's strongest counter-argument). The builder's own 150 are
cleaner than what people really type; yours are the ones that tell us whether filing works.

## What to write

Write what you would really type into a notes app in passing, the way you would type it:
lowercase, typos, half sentences, numbers without "€", "tmrw", "fri". Mix them:

- things to do, with or without a day or time ("dentist thurs 3", "call the bank")
- money spent ("lidl 23,40", "uber home 12")
- trips ("Lisbon 9-12 Oct, ~500")
- changes to things you already have ("move the dentist to friday", "groceries were 45")
- one or two things that are not really filable ("ugh", "the thing with Paulo")

## How to hand them in

The easiest way: a plain list, one capture per line, with the date you imagine writing it,
for example `2026-02-23  paid 42 for groceries`. Send it to the builder, who turns each line
into a case and writes the expected ops. Please don't look at `captures.jsonl` first.

If you prefer to write the cases yourself, add lines to `eval/captures.jsonl` in this shape
(one JSON object per line):

```json
{"id": "o001", "today": "2026-02-23", "tz": "Europe/Lisbon", "context": {"tasks": [], "expenses": [], "trips": []},
 "text": "paid 42 for groceries", "source": "typed", "author": "<your first name>",
 "expected_ops": [{"op": "create_expense", "amount_cents": 4200, "date": "2026-02-23",
                   "category": "Groceries", "description": "Groceries"}]}
```

- `author` is anything except `builder`; the scorer reports your cases separately.
- `source` is `paste` for text pasted from elsewhere (it may only create items).
- Ops and categories: `docs/spec.md`, "Op schema". Something that cannot be filed expects a
  single `{"op": "note", "text": "<the words>", "suggestions": []}`.
- Optional: `captured_at` (`YYYY-MM-DDTHH:MM:SS`, default 09:00 on `today`) and `comment`.

`python -m pytest tests/test_eval.py` checks every case is well formed and its expected ops
pass the Validator.
