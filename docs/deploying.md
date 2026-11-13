# Building, reviewing and deploying Dumpit

How to take Dumpit from where it is now to a live app on your phone and your computer,
using Project Kit 0.8.0+. Everything runs from **Claude Code on your own computer**:
deploying needs your Google Cloud login, which a cloud session does not have.

Where it stands: plan done; judge review waived; slices 1, 3 and 4 built; slice 2 blocked on
an API key and 50 captures; slices 5 to 14 to build. CI and the deploy setup are in place
(`.github/workflows/ci.yml`, `pk ship config`).

## 0. Once: get the tools and accounts

On your computer:

```bash
claude plugin update project-kit        # or: claude plugin install project-kit
git clone https://github.com/miricoder/project-kit dumpit
cd dumpit && git checkout dumpit
```

| Account | What for | Where |
|---|---|---|
| Anthropic API key | the real filer, and slice 2's accuracy baseline | console.anthropic.com |
| 2 Postgres databases, EU | staging data and production data, kept apart | Neon free tier, region eu-central-1 |
| Email sending (SMTP) | sign-in links | Postmark, Resend, or your mail provider |
| Google Cloud project with billing on | hosting (Cloud Run, Europe) | console.cloud.google.com; install `gcloud`, then `gcloud auth login` |

Never paste a key into the chat. The scripts below ask for each one at a hidden prompt.

One task only a person can do: **someone other than you writes 50 real captures** for
slice 2 (`eval/WRITING_CAPTURES.md`).

## 1. Optional: the independent review

The judge review was waived because the OpenAI account had no credit. To have the plan
judged before building ten more slices on it, add credit (or set up paste seats), then in
Claude Code say:

> /project-kit:handover, then /project-kit:verdict

If the judges ask for fixes, the spec and backlog change first. Skipping it is allowed. The
test and security gates still review the code before launch.

## 2. See it online early (staging)

You can do this while slices are still being built.

```bash
gcloud config set project <your-project-id>
sh scripts/setup-secrets.sh staging          # asks for the API key, staging DB URL, SMTP URL

export DUMPIT_ALLOWED_EMAIL=you@example.com  # the one email that may sign in
export DUMPIT_MAIL_FROM=dumpit@yourdomain.com
sh scripts/deploy.sh staging                 # builds the image, prints the URL
```

Then, in Claude Code, record it (`pk ship` checks the URL answers before recording it):

> /project-kit:devops, record the staging deploy at <url>

**Open it on your phone:** the URL in Safari → Share → **Add to Home Screen**. On Android,
use Chrome → menu → **Install app**. **On your computer:** the same URL in any browser.
Sign in with the email you set; the link arrives by email.

## 3. Finish the build

In Claude Code, in the `dumpit` folder:

> /project-kit:pipeline

Dumpit is in **yolo** mode, so `/build` goes slice after slice (test-first; `pk slice done`
decides). It stops when a slice is blocked (it tells you what it needs), when the budget is
reached (`pk state budget --max 50` raises it), or when every slice is done. Expect several
sessions. Say `/project-kit:pipeline` again to resume; it continues from `pipeline.json`.

After each few slices, redeploy staging (`sh scripts/deploy.sh staging`) and try it.

## 4. Release, test gate, security gate

When the last slice is done the pipeline moves on by itself:

| Step | What happens | Who decides |
|---|---|---|
| `/devops` | writes `CHANGELOG.md`, deploys the final commit to staging, tags `v1.0.0` | `pk ship release`, `pk ship done devops` |
| `/test` | full suite, plus all 60 acceptance scenarios mapped to tests; `docs/test-report.md` | `pk ship test` |
| `/security` | threat model, a secret scan of every commit, dependency audit; `docs/security-audit.md` | `pk ship audit` |

For a deeper code review alongside these, run Claude Code's built-in `/security-review`.
CI runs every test on each push to `dumpit` (GitHub → Actions).

## 5. Launch

```bash
sh scripts/setup-secrets.sh production       # production DB (not the staging one), same key/SMTP or new ones
```

> /project-kit:launch

It asks before deploying to production, then deploys `v1.0.0` (`sh scripts/deploy.sh production`)
and rehearses a rollback on the real service:

```bash
gcloud run revisions list --service dumpit --region europe-west1
gcloud run services update-traffic dumpit --region europe-west1 --to-revisions <previous>=100   # roll back
gcloud run services update-traffic dumpit --region europe-west1 --to-latest                     # restore
```

`pk ship done launch` records the launch only when production runs the release over https,
answers now, and the rollback was recorded. Then add the production URL to your Home Screen
as in step 2.

## Checking where you are

| Command | Shows |
|---|---|
| `pk state next` | the next phase and what blocks it |
| `pk slice list` | every slice and its status |
| `pk ship status` | deploy target, staging and production deploys, release, gates |
| `pk graph serve` | the whole pipeline as a graph at http://127.0.0.1:7474 |
