# Dumpit for Google Cloud Run (docs/spec.md "Hosting"): one image with the service and the
# built web app, served from one origin. Secrets (ANTHROPIC_API_KEY, DUMPIT_DATABASE_URL,
# DUMPIT_SMTP_URL) come from Secret Manager at deploy time, never from this image.

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir anthropic==2.3.0 fastapi==0.115.6 uvicorn==0.34.0 \
    "psycopg[binary]==3.2.3"
COPY dumpit_ops/ dumpit_ops/
COPY service/ service/
COPY --from=web /web/dist web/dist
ENV PORT=8080
CMD ["sh", "-c", "uvicorn service.server:app --host 0.0.0.0 --port ${PORT}"]
