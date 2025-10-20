FROM ghcr.io/astral-sh/uv:python3.11-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/workspace"

WORKDIR /workspace

# Copy deps & metadata first for caching
COPY pyproject.toml uv.lock README.md ./

# Install deps but DO NOT install the project itself
RUN uv sync --frozen --no-install-project

# Bring in the rest (code and notebooks)
# This layer rebuilds whenever source code changes
COPY . .

EXPOSE 8888
CMD ["uv", "run", "jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--NotebookApp.token=", "--allow-root"]
