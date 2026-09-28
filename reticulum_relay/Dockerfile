FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN adduser --system --group --no-create-home appuser

COPY reticulum_relay/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY reticulum_relay/app ./app
COPY reticulum_relay/pages ./pages

RUN mkdir -p /data/rns /data/lxmf /data/state \
    && chown -R appuser:appuser /data

USER appuser
EXPOSE 8082 4242
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8082/health || exit 1
CMD ["python", "-m", "app.main"]
