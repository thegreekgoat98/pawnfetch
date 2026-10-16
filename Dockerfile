FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first so this layer is cached until pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev --group web

COPY src ./src
COPY web ./web
RUN uv sync --locked --no-dev --group web

RUN useradd --create-home app
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uvicorn", "web.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
