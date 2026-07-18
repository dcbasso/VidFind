FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask requests

COPY app.py .
COPY config.json .
COPY templates/ templates/
COPY static/ static/
COPY assets/ assets/

EXPOSE 8080
CMD ["python", "app.py"]
