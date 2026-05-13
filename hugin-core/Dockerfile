FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt .
RUN apk add --no-cache cairo cairo-dev pango pango-dev gdk-pixbuf font-noto fontconfig curl
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN adduser -D appuser
USER appuser

EXPOSE 5100
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:5100/api/health || exit 1

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5100", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
