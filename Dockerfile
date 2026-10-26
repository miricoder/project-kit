# Filing service for Google Cloud Run (docs/spec.md, "Filing service host").
# ANTHROPIC_API_KEY comes from Secret Manager at deploy time, never from this image.
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir anthropic==2.3.0 fastapi==0.115.6 uvicorn==0.34.0
COPY dumpit_ops/ dumpit_ops/
COPY service/ service/
ENV PORT=8080
CMD ["sh", "-c", "uvicorn service.app:app --host 0.0.0.0 --port ${PORT}"]
