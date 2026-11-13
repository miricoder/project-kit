# Dumpit for Google Cloud Run (docs/spec.md "Hosting"): one image with the service and the
# built web app, served from one origin. Secrets (ANTHROPIC_API_KEY, DUMPIT_DATABASE_URL,
# DUMPIT_SMTP_URL, DUMPIT_ALLOWED_EMAIL, DUMPIT_MAIL_FROM) come from Secret Manager at deploy
# time, never from this image. APP_VERSION (scripts/version.sh) is baked into both the web app
# and the service, so the update notice always compares like with like.
ARG APP_VERSION=dev

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY dumpit_ops/ dumpit_ops/
COPY service/ service/
COPY --from=web /web/dist web/dist
COPY CHANGELOG.md ./
ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION PORT=8080
CMD ["sh", "-c", "uvicorn service.server:app --host 0.0.0.0 --port ${PORT}"]
