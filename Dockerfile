FROM python:3.12.16 AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN python -m venv .venv
COPY requirements.txt ./
RUN .venv/bin/pip install -r requirements.txt

FROM python:3.12.16-slim
WORKDIR /app
COPY --from=builder /app/.venv .venv/
COPY . .

# Use Gunicorn production WSGI server instead of flask run
CMD ["/app/.venv/bin/gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app:app"]
