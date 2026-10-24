FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /repo

COPY pyproject.toml uv.lock ./
COPY services/api/pyproject.toml services/api/pyproject.toml

RUN uv sync --frozen --no-dev --package geo-track-api

COPY services/api services/api
COPY wire /repo/wire

WORKDIR /repo/services/api

ENV PATH="/repo/.venv/bin:$PATH" \
    PYTHONPATH=/repo/services/api:/repo \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
