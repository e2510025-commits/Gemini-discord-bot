FROM python:3.11-slim
WORKDIR /app

# system deps for ffmpeg and libs
RUN apt-get update && apt-get install -y ffmpeg git curl && rm -rf /var/lib/apt/lists/*

COPY ./bot /app
WORKDIR /app
RUN python -m venv .venv && . .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

ENV PYTHONUNBUFFERED=1
CMD ["/app/.venv/bin/python","main.py"]
