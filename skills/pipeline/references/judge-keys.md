# Asking for a judge key

The judge panel needs three seats from three model families, none of them Anthropic. A
judging round does not start until the user has given **at least one** judge key; the
other seats may be filled by pasting the brief by hand. Keys are never in a repository:
the plugin's is public and a project is a git repository too. They live in
`~/.claude/project-kit/.env`, mode 600, written only by `pk keys`.

Run this whenever a skill says "ask for a judge key". Resolve `pk` to its literal path
first, as the calling skill describes.

## 1. Check

```bash
pk keys status
```

`ready: true`: nothing to ask, carry on. A panel of three paste seats is only ever
configured on purpose (step 5), so it counts.
`ready: false`: go on.

## 2. Ask: explicitly, with the AskUserQuestion tool

Ask both questions in one call. Do not skip this in any mode, `yolo` included: no key, no
judging round, and only the user can supply one.

1. **"Judging needs an API key from at least one AI provider other than Anthropic. Which
   one can you provide?"** (header `Judge key`). Options, from `addable` in the status
   output: `OpenAI (Recommended)`, `Google Gemini`, `Moonshot (Kimi)`. xAI, DeepSeek and
   Mistral are accepted through "Other". If `key_seats` is already non-empty, ask for an
   *additional* key instead and say which families already sit.
2. **"How should the remaining seats be filled?"** (header `Other seats`). Options:
   `Paste them by hand (Recommended)`: you paste the brief into those providers' chats
   and give back the reply; `I'll add more keys`.

Say in the question text that the key goes into a private file on this machine, not
the repository and not the chat.

## 3. Have the user store the key themselves

Tell the user to run, **in their own terminal** (input is hidden, nothing is echoed):

```bash
<literal pk path> keys add <family> --live
```

`--live` probes the seat with a tiny real call, so a key with no credit is caught now
rather than mid-round. In a cloud session with no terminal of their own, they set the
variable (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `MOONSHOT_API_KEY`, …) as a secret in the
session's environment settings and start a new session; `pk` reads it from the process
environment.

Then wait for them to say it is done, and run `pk keys status` again.

Hard rules:

- **Never ask for the key in the chat**, never put it on a command line or in any file in
  a project, and never print it back.
- If the user pastes a key into the chat anyway, store it at once with
  `pk keys add <family> --stdin` fed from a quoted heredoc. Then tell them in one line that
  the key is now in this conversation's transcript and that they should rotate it once
  judging is done.
- Never accept an Anthropic key; `pk keys` refuses it.

## 4. Fill the rest

If they chose to paste the remaining seats:

```bash
pk keys paste-rest
```

Then `pk keys status` must show `ready: true`. Tell the user which families they will
paste for, and that `/handover` will hand them the brief.

## 5. If they decline

No key at all: say that the judge gate stays shut and development cannot start, then
stop. Do not seat three paste judges on your own initiative, and never judge the plan
yourself. If the user *asks* for an all-paste panel, run `pk keys paste-rest` and carry
on.
