FROM python:3.10-slim

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system -e ".[dev]"

# Default command — overridden in docker-compose
CMD ["uvicorn", "circleback.main:app", "--host", "0.0.0.0", "--port", "8000"]
