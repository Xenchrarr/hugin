FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ecoflow_client.py .
COPY service ./service

RUN useradd -r appuser
USER appuser

EXPOSE 5080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:5080/health || exit 1

CMD ["python", "-m", "service.main"]
