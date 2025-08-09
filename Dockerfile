# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install --upgrade pip && pip install .

CMD ["python", "-m", "src.newsletter_bot"]
