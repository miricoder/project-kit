# Deploy targets

These are the commands each `pk ship config --target` value means. They run with the
**user's** credentials. When this session has none, give the user these commands to run on
their own computer.

In every recipe, `<svc>` is the service name and `<url>` is the address the platform prints.
Record each deploy afterwards:

```bash
pk ship -C . record staging --url <url>        # or production, from /launch
```

Staging and production are two separate services, for example `<svc>-staging` and `<svc>`,
each with its own database. Never point staging at production data.

## cloudrun: Google Cloud Run (container, scales to zero)

Needs: a Google Cloud project with billing, the `gcloud` CLI and `gcloud auth login`. The
repo needs a `Dockerfile` that listens on `$PORT`.

```bash
gcloud config set project <project-id>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

# once per secret: the value is read from the user's terminal, never from a file in the repo
printf %s "$DATABASE_URL" | gcloud secrets create <svc>-database-url --data-file=-
#   (update an existing one with: gcloud secrets versions add <name> --data-file=-)

gcloud run deploy <svc>-staging --source . --region europe-west1 --allow-unauthenticated \
  --set-secrets DATABASE_URL=<svc>-database-url:latest,ANTHROPIC_API_KEY=<svc>-anthropic:latest \
  --set-env-vars APP_ENV=staging
```

- **URL:** printed as `Service URL:`. Read it later with
  `gcloud run services describe <svc>-staging --region europe-west1 --format 'value(status.url)'`.
- **Version:** each deploy is a revision. Record the git commit with `--version`, which
  defaults to HEAD.
- **Logs:** `gcloud run services logs read <svc>-staging --region europe-west1 --limit 50`
- **Rollback:**
  `gcloud run revisions list --service <svc> --region europe-west1` lists the revisions.
  Then `gcloud run services update-traffic <svc> --region europe-west1 --to-revisions <previous-revision>=100`.
- **Restore:** `gcloud run services update-traffic <svc> --region europe-west1 --to-latest`

## fly: Fly.io (container, always-on machines)

Needs: `flyctl` and `fly auth login`.

```bash
fly launch --no-deploy --name <svc>-staging --region ams      # once; writes fly.toml
fly secrets set -a <svc>-staging DATABASE_URL=... ANTHROPIC_API_KEY=...   # the user types these
fly deploy -a <svc>-staging
```

- **URL:** `https://<svc>-staging.fly.dev`
- **Logs:** `fly logs -a <svc>-staging`
- **Rollback:** `fly releases -a <svc> --image` lists the releases. Then
  `fly deploy -a <svc> --image <previous image>`.
- **Restore:** `fly deploy -a <svc> --image <current image>`

## render: Render (container or native runtime)

Needs: a Render account connected to the GitHub repository. Deploys come from git pushes
or from the dashboard, so the user runs them.

- Create a Web Service from the repo with branch `staging` and health check path = the
  `--health` path. Set the secrets in the service's Environment tab.
- **URL:** `https://<svc>-staging.onrender.com`
- **Rollback:** Dashboard → Events → pick the earlier deploy → Rollback.
- **Restore:** Redeploy the latest commit.

## docker: any host that runs a container

Needs: SSH access to the host and Docker on it. Put a reverse proxy in front for https
(Caddy issues certificates by itself).

```bash
docker build -t <svc>:<commit> .
docker save <svc>:<commit> | ssh <host> docker load
ssh <host> "docker rm -f <svc>-staging; docker run -d --name <svc>-staging --restart unless-stopped \
  --env-file /etc/<svc>/staging.env -p 8081:8080 <svc>:<commit>"
```

- **Logs:** `ssh <host> docker logs --tail 50 <svc>-staging`
- **Rollback:** run the previous `<svc>:<commit>` image the same way.
- **Restore:** run the current image again.

## other

Any other platform works the same way: deploy by its own means, then `pk ship record` the
URL. A rollback is whatever returns production to the previous version. The script checks
the result, not the method.

## Continuous deploy

Iterations should ship without a person running commands: **CI deploys staging after the
tests pass, on every push**, and production on a release tag, behind an approval.
`pk ship done devops` refuses until a CI file deploys to staging (a job that names both
"deploy" and "staging").

The shape, for any target, in `.github/workflows/ci.yml`:

```yaml
on: { push: { branches: [main], tags: ['v*'] }, pull_request: {} }
jobs:
  test:  { ... runs the project's test command ... }
  deploy-staging:
    needs: test
    if: github.event_name == 'push' && startsWith(github.ref, 'refs/heads/') && vars.DEPLOY_READY != ''
    environment: staging
    steps: [checkout, <log in to the target>, run: sh scripts/deploy.sh staging]
  deploy-production:
    needs: test
    if: startsWith(github.ref, 'refs/tags/v') && vars.DEPLOY_READY != ''
    environment: production     # add yourself as a Required reviewer in GitHub > Settings > Environments
    steps: [checkout, <log in to the target>, run: sh scripts/deploy.sh production]
```

The `vars.…` condition skips the deploy jobs until the user has set the target up, so CI stays
green before that. Keep one `scripts/deploy.sh <env>` that both CI and a person can run.

How CI logs in, without storing a key where one can be avoided:

- **cloudrun:** Workload Identity Federation. A one-time script, run in Cloud Shell, does the
  setup:
  - creates a pool whose GitHub provider is limited to the repository by
    `--attribute-condition "assertion.repository == 'owner/repo'"`;
  - creates a deployer service account with `roles/run.admin` and
    `roles/artifactregistry.writer`, plus `roles/iam.serviceAccountUser` on the runtime account;
  - grants `roles/iam.workloadIdentityUser` to
    `principalSet://…/attribute.repository/owner/repo`.

  The job then uses `google-github-actions/auth@v2` with `workload_identity_provider` and
  `service_account`, both kept as repository *variables* because they are not secret.
  Build with `docker build`, push to Artifact Registry, and run `gcloud run deploy --image`.
  A worked example is the Dumpit project's `scripts/setup-cloud.sh` and `scripts/deploy.sh`.
- **fly:** `fly tokens create deploy` makes a deploy token. Store it as the repository secret
  `FLY_API_TOKEN`, then use `superfly/flyctl-actions/setup-flyctl` and run `fly deploy`.
- **render:** turn on Auto-Deploy for the branch in Render, so no CI job is needed. Keep a CI
  job that waits for the health check after a push, so `pk ship` can see a staging deploy
  step.

**Stamp every build with its version** (`git describe --tags`, or the newest CHANGELOG version
plus the commit), and bake it into the image. Then the running service can report it, and a
web app can tell its user it was updated.

## Upkeep

Run these once per environment, right after its first deploy. `/launch` checks with the
user that each one is in place for production.

| What | Why | cloudrun |
|---|---|---|
| Uptime alert | an email when the app stops answering | `gcloud monitoring uptime create` on the health path, plus an alert policy on `uptime_check/check_passed` sent to an email channel |
| Budget alert | an email before any real cost | `gcloud billing budgets create … --threshold-rule percent=0.2` |
| Dependency updates | libraries kept current, each update tested by CI | `.github/dependabot.yml` for each ecosystem (`pk ship done devops` checks it exists). GitHub reads it only from the **default branch**. |
| Rollback | a bad release undone in a minute | the target's Rollback command above, rehearsed at `/launch` |

## The web app on a phone

A web app that answers over https on a public URL is reachable from any phone and computer.
With a web manifest and a service worker it installs like an app, with no App Store:
- iPhone: Safari → Share → Add to Home Screen.
- Android: Chrome → ⋮ → Install app.
- Computer: Chrome or Edge, using the install icon in the address bar.

An access rule in the app (such as an allowlist of sign-in emails) keeps it private while the
address is public.
