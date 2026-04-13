FROM python:3.12-alpine
LABEL authors="emil"

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]