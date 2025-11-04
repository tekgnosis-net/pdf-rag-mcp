# syntax=docker/dockerfile:1

FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY src/frontend/package*.json ./
RUN npm install
COPY src/frontend ./
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu124
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libgl1 libglib2.0-0 curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/backend ./src/backend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV DATA_DIR=/app/data \
    FRONTEND_DIST_PATH=/app/frontend/dist

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "src.backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
