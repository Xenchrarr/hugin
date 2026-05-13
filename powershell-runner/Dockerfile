FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends git curl gnupg \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/microsoft.list \
    && apt-get update && apt-get install -y --no-install-recommends powershell \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY src ./src
COPY scripts ./scripts
RUN mkdir -p /app/logs \
    && touch /app/logs/response.txt

EXPOSE 6001
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:6001/api/health || exit 1
CMD ["python3", "app.py"]