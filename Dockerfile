FROM python:3.13-slim AS builder

RUN apt-get update \
 && apt-get install -y --no-install-recommends binutils \
 && rm -rf /var/lib/apt/lists/* \
 && pip install uv

 WORKDIR /app

ENV UV_PYTHON_DOWNLOADS=0 \
    UV_CACHE_DIR=/root/.cache/uvm \
    UV_SYSTEM_PYTHON=1 \
    UV_SKIP_WHEEL_FILENAME_CHECK=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv sync --no-install-project --group build --no-dev --frozen

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv run pyinstaller --onefile app.py \
        --name app \
        --add-data "templates:templates" \
        --add-data "static:static" \
        --distpath ./ \
        --clean

FROM python:3.13-slim AS runtime

RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*
 
WORKDIR /app

COPY --from=builder /app/app /app/app

RUN chmod +x /app/app

EXPOSE 8080

CMD ["/app/app"]