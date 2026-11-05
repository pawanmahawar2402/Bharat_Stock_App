# Single container for Render (or any Docker host):
#   FastAPI backend on 127.0.0.1:8001 (internal), Next.js frontend on $PORT (public).
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PORT=7860 PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////app/backend/bharatstock.db
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY data/ data/
COPY --from=web /web /app/frontend
COPY start.sh start.sh
RUN chmod +x start.sh \
 && useradd -m appuser \
 && mkdir -p /app/backend \
 && chown -R appuser /app
USER appuser
EXPOSE 7860
CMD ["./start.sh"]
