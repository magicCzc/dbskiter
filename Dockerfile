FROM python:3.11-slim

LABEL maintainer="MagiCzc <magiczc@139.com>"
LABEL description="dbskiter - Database AIOps Assistant"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files
COPY pyproject.toml setup.py README.md ./
COPY dbskiter/ ./dbskiter/

# Install the package
RUN pip install --no-cache-dir -e . \
    && pip install --no-cache-dir psycopg2-binary

# Create volume mount points
VOLUME ["/app/.env", "/app/backups", "/app/runtime_data", "/app/logs"]

# Set entrypoint
ENTRYPOINT ["dbskiter"]
CMD ["--help"]