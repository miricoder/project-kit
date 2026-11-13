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

## The web app on a phone

A web app that answers over https on a public URL is reachable from any phone and computer.
For a home-screen app on iPhone: open the URL in Safari, then Share → Add to Home Screen.
On Android: open it in Chrome, then menu → Install app.
