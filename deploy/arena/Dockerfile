ARG PYTHON_IMAGE
ARG NODE_IMAGE
ARG RUST_IMAGE
FROM ${NODE_IMAGE} AS web
WORKDIR /web
COPY rotk_env/rendering/web/client/package*.json ./
RUN npm ci --ignore-scripts
FROM ${RUST_IMAGE} AS rust
FROM ${PYTHON_IMAGE} AS builder
COPY --from=rust /usr/local/cargo /usr/local/cargo
COPY --from=rust /usr/local/rustup /usr/local/rustup
ENV PATH="/usr/local/cargo/bin:$PATH" RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.5
WORKDIR /app
COPY . .
RUN uv sync --frozen --extra native --extra arena --extra arena-hub --no-dev --no-editable
# Only the private routing application is hosted, not the unrelated public REST APIs.
RUN git clone https://github.com/Coldmooon/GameServer.git /hub && cd /hub && git checkout --detach 5e26985ee86620e120ef792a2a4c01e63a847e8c && rm -rf .git
FROM ${PYTHON_IMAGE} AS runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /app /app
COPY --from=web /web/node_modules /app/rotk_env/rendering/web/client/node_modules
RUN useradd --create-home --uid 10001 arena && mkdir -p /app/.arena && chown arena:arena /app/.arena
USER arena
ARG ENV_REVISION
ENV ARENA_ENV_REVISION=${ENV_REVISION}
CMD ["python", "-m", "starbench_arena", "--host", "0.0.0.0"]
FROM runtime AS hub
COPY --from=builder --chown=arena:arena /hub /hub
ENV PYTHONPATH=/hub:/app
CMD ["python", "-m", "uvicorn", "deploy.arena.hub_app:app", "--host", "0.0.0.0", "--port", "8000"]
