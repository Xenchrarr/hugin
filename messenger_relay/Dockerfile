FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN adduser --system --no-create-home appuser

COPY messenger_relay/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY messenger_relay/app ./app
RUN mkdir -p /data && chown appuser /data

USER appuser
EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8081/health || exit 1
CMD ["python", "-m", "app.main"]
