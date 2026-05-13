FROM python:3.12-alpine
LABEL authors="emil"

RUN apk add --no-cache curl

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5060
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:5060/api/telegram/health || exit 1
CMD ["python", "main.py"]