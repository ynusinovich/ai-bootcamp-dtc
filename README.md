# AI Bootcamp – Local Dev (uv + Docker + Ollama)
- **uv** for Python dependency management
- **Jupyter** for development
- **Ollama** (GPU) for local LLMs

## Prereqs
- Docker + Docker Compose
- (GPU use) NVIDIA drivers + NVIDIA Container Toolkit
- A `.env` file in this folder with your secrets (see sample below)

## .env example
```env
# OpenAI
OPENAI_API_KEY=sk-...
```

## Common Commands

### Start Jupyter + Ollama (GPU)
```bash
docker run --rm -v "$PWD:/w" -w /w ghcr.io/astral-sh/uv:python3.11-bookworm uv lock
docker compose up -d --build
docker exec -it ai-bootcamp-dtc-ollama-1 ollama pull llama3.1:8b
```

### Stop containers (keep data/volumes)
```bash
docker compose stop
```

### Stop & remove containers (keep volumes)
```bash
docker compose down
```

### Rebuild the dev image
```bash
docker compose build --no-cache dev
docker compose up -d dev
```

### Clear cache/wipe volumes
DANGER: This deletes persisted data (like Ollama models).
```bash
docker compose down -v  # remove containers + named volumes
docker volume prune -f  # remove dangling volumes
docker builder prune -af  # clear build cache
```

## Add/Remove Python Packages (with uv)

### Add a package
```bash
docker compose exec dev uv add pandas
```

### Remove a package
```bash
docker compose exec dev uv remove pandas
```
