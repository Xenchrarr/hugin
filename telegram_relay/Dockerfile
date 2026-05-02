FROM python:3.12-slim-bullseye

WORKDIR /app

RUN adduser --system --no-create-home appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p /app/data/tdlib && chown -R appuser /app/data

USER appuser

CMD ["python", "-m", "app.main"]
