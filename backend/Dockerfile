FROM python:3.14-slim

ARG APP_VERSION=dev
ARG APP_COMMIT=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=$APP_VERSION \
    APP_COMMIT=$APP_COMMIT

WORKDIR /app
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/src ./backend/src
RUN pip install --no-cache-dir ./backend

COPY backend/alembic.ini ./backend/alembic.ini
COPY backend/migrations ./backend/migrations

RUN useradd --system --no-create-home app
USER app

WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
