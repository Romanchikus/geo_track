FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /repo

COPY pyproject.toml uv.lock ./
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY canary_tests/pyproject.toml canary_tests/pyproject.toml

RUN uv sync --frozen --no-dev --package geo-track-canary

COPY canary_tests canary_tests
COPY wire /repo/wire

ENV PATH="/repo/.venv/bin:$PATH" \
    PYTHONPATH=/repo \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "canary_tests.bench_devices", "--base-url", "http://nginx", "--loops", "0", "--devices-file", "/data/devices.pkl"]
