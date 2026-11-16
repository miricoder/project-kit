# Running the filing eval on your Mac

The eval sends the test messages in `eval/captures.jsonl` to Claude, checks what comes back
against the right answer for each, and prints a score. It runs only the filing part of
Dumpit, on your Mac: no database, no website, no Google Cloud. A full run costs well under
$1 of Anthropic API credit.

## Step 1: Get an Anthropic API key (once)

1. Go to **console.anthropic.com** and sign in or sign up.
2. **Settings → Billing → Buy credits**: $5 is plenty. This is separate from a claude.ai
   Pro or Max plan and does not use your chat allowance.
3. **Settings → API Keys → Create Key**, name it `dumpit`, then **Copy**. It starts with
   `sk-ant-` and is shown only once. Keep it in a password manager, never in a chat.

## Step 2: Check Python (once)

Open the **Terminal** app and run:

```bash
python3 --version
```

You need **3.11 or newer**. If it says 3.9 or "not found", install it with Homebrew
(`brew install python@3.13`, after installing Homebrew from brew.sh), then open a new
Terminal window and check again.

## Step 3: Get the code, on the `dumpit` branch

Dumpit's code lives only on the **`dumpit`** branch of `miricoder/project-kit`. The other
branches hold the Project Kit tool itself and have no eval.

If you have **not** cloned the repository yet:

```bash
cd ~
git clone -b dumpit https://github.com/miricoder/project-kit.git dumpit
cd dumpit
```

If you **already have** a clone (for example on `feat/per-project-panel-override`):

```bash
cd path/to/your/project-kit          # the folder of your existing clone
git status                           # commit or stash any changes first
git fetch origin
git checkout dumpit
git pull origin dumpit
```

Check you are in the right place: `git branch --show-current` prints `dumpit`, and `ls`
shows `eval`, `service` and `dumpit_ops`.

## Step 4: Install the packages (once)

From the `dumpit` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

`(.venv)` now shows at the start of the prompt. In a new Terminal window, run
`source .venv/bin/activate` again from this folder.

## Step 5: Set the API key (each new Terminal window)

Pick one:

**A. Type it for this window only (simplest):**

```bash
export ANTHROPIC_API_KEY=sk-ant-...your key...
```

The key is forgotten when you close the window.

**B. Keep it in a `.env` file in this folder:**

```bash
printf 'ANTHROPIC_API_KEY=%s\n' 'sk-ant-...your key...' > .env
chmod 600 .env
set -a; . ./.env; set +a          # loads it; run this in each new window
```

`.env` is ignored by git, so it is never committed. Do not use Project Kit's
`~/.claude/project-kit/.env`: that one holds judge keys and the eval does not read it.

Check it is set without showing it:

```bash
[ -n "$ANTHROPIC_API_KEY" ] && echo "key is set" || echo "key is missing"
```

## Step 6: Trial run (20 messages, under one cent)

```bash
python -m eval.score --limit 20
```

It prints a line per message and a summary at the end. If it stops with an error, send the
error text (never the key).

## Step 7: Full run

```bash
python -m eval.score
```

It sends all the messages (150 now, 200 once others' messages are added), prints the score
overall and per kind, the mean cost per message, and writes `eval/report.json`.

## Step 8: Send back the result

Copy the summary printed at the end into the chat. To share the full detail as well:

```bash
git checkout -b eval-baseline
git add eval/report.json
git commit -m "First filing baseline"
git push -u origin eval-baseline
```

Claude then records it in `eval/BASELINE.md`.

## If something goes wrong

| You see | Do |
|---|---|
| `ANTHROPIC_API_KEY is not set` | Repeat step 5 in this window |
| `No module named ...` | `source .venv/bin/activate`, then step 4 again |
| `401` or `authentication_error` | The key is wrong or revoked: create a new one (step 1) |
| `credit balance is too low` or `insufficient` | Add credit (step 1, Billing) |
| `error: pathspec 'dumpit' did not match` | Run `git fetch origin` first (step 3) |
