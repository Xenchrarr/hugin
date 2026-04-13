FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc libc6-dev curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY src ./src
COPY sql ./sql
COPY init ./init

RUN useradd -r appuser
USER appuser

EXPOSE 6000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:6000/api/connection_status/health || exit 1

CMD ["python3", "app.py"]