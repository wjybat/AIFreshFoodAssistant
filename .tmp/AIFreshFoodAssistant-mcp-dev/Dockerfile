FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app

# Install exactly the dependency set recorded for the isolated MCP service.
COPY pyproject.toml uv.lock ./
RUN pip install "uv>=0.6,<1" \
    && uv sync --frozen --no-dev --no-install-project

COPY --chown=app:app server.py data_access.py ./
COPY --chown=app:app data/fresh_food_dev.sqlite3 ./data/fresh_food_dev.sqlite3

USER app

EXPOSE 8765

CMD ["/app/.venv/bin/python", "server.py", "--transport", "streamable-http", "--port", "8765"]