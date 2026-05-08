FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY src ./src

RUN useradd -r appuser \
    && usermod -aG lp appuser

USER appuser

EXPOSE 6002
CMD ["python3", "app.py"]
