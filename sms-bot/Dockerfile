FROM python:3.13-slim
LABEL authors="emil"

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5050
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:5050/api/sms/health || exit 1
CMD ["python", "main.py"]