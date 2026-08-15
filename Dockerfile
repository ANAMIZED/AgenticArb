FROM python:3.12-slim

WORKDIR /app

# System deps for scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src/ ./src/
COPY configs/ ./configs/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e .

# Default: run full verification so a fresh container proves the system works
CMD ["python", "-m", "agenticarb.cli", "verify"]
