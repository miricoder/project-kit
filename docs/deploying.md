# Putting Dumpit online

Dumpit runs on **Google Cloud Run** (Europe), free at this scale. After a one-time setup,
every change that passes the tests goes live on **staging** by itself. **Production** goes
live when a release is tagged and you approve it. The installed app updates itself and tells
you what changed.

Nothing needs installing on your computer. The setup runs in **Google Cloud Shell**, a
terminal in your browser with everything already in it.

## 1. Accounts (once)

| What | Where | Note |
|---|---|---|
| Anthropic API key | console.anthropic.com → Billing (add $5) → API Keys → Create | shown once; keep it for step 3 |
| Database | neon.tech → New Project, region **Europe (Frankfurt)** → copy the `postgresql://…` string | make two: `dumpit-staging`, `dumpit-prod` |
| Email sending | Gmail: turn on 2-Step Verification, then myaccount.google.com/apppasswords → create "Dumpit" | gives 16 letters |
| Google Cloud | console.cloud.google.com → New Project (note the **Project ID**) → Billing → link a card | about €0 a month; a budget alert emails you first |

## 2. Google Cloud setup (once, about 5 minutes)

Open console.cloud.google.com and click **>_** (Activate Cloud Shell) at the top right. In the
terminal that opens:

```bash
gcloud config set project YOUR-PROJECT-ID
git clone -b dumpit https://github.com/miricoder/project-kit dumpit && cd dumpit
sh scripts/setup-cloud.sh miricoder/project-kit
```

It ends by printing four values. In GitHub, open the repository, then **Settings → Secrets
and variables → Actions → Variables → New repository variable**, and add each one:
`GCP_PROJECT`, `GCP_REGION`, `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`.

Then, still in GitHub: **Settings → Environments → New environment → `production` →
Required reviewers → add yourself**. Production deploys then wait for your click.

## 3. Your settings (once per environment)

In Cloud Shell:

```bash
sh scripts/setup-secrets.sh staging
```

It asks for five things, with your typing hidden:
- the Anthropic key;
- the **staging** database string;
- the email-sending address, `smtps://YOU%40gmail.com:THE16LETTERS@smtp.gmail.com:465` (the `%40` stands for the `@`);
- the sender address, your Gmail;
- the one email allowed to sign in.

## 4. First deploy

Either push any change to the `dumpit` branch, or in GitHub open **Actions → Dumpit CI → the
latest run → Re-run all jobs**. After the tests pass, the **deploy-staging** job prints the
app's address (`https://dumpit-staging-….run.app`). The same address is in Cloud Run, in the
Cloud Console.

Then, once, in Cloud Shell: `sh scripts/setup-uptime.sh staging YOUR-EMAIL`. You'll then
get an email if the app stops answering.

## 5. Install it

- **Android (Chrome):** open the address → sign in with the emailed link → **⋮ → Install app**
  (or **Add to Home screen**).
- **iPhone (Safari):** open the address → sign in → **Share → Add to Home Screen**.
- **Computer (Chrome or Edge):** open the address → the **install icon** at the right of the
  address bar → Install. It opens in its own window like a desktop app.

Sign in once on each device. The same data shows everywhere.

## After that: changes, releases, upkeep

| What happens | How |
|---|---|
| A change is pushed and the tests pass | staging redeploys by itself |
| You open the app after an update | "Updated to 0.1.0-abc123" and what changed, from `CHANGELOG.md` |
| The app is open when a new version lands | "A new version of Dumpit is ready" → **Update now** |
| A release is tagged (`pk ship release v1.0.0`, from `/devops`) | the production deploy waits for your approval in GitHub → Actions |
| Production is first set up | `sh scripts/setup-secrets.sh production` (the **prod** database), then the tag, then `sh scripts/setup-uptime.sh production YOUR-EMAIL` |
| A library has an update | Dependabot opens a weekly pull request; CI tests it |
| Something goes wrong after a deploy | Cloud Run → dumpit → Revisions → send 100% of traffic to the previous one (the `/launch` rollback drill rehearses this) |
| Spending goes above €1 | the budget emails you (20% of €5) |
