FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ecoflow_client.py .
COPY service ./service

RUN useradd -r appuser
USER appuser

CMD ["python", "-m", "service.main"]
