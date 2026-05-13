FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY src ./src

RUN useradd -r appuser \
    && usermod -aG lp appuser

USER appuser

EXPOSE 6002
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:6002/api/health || exit 1
CMD ["python3", "app.py"]
