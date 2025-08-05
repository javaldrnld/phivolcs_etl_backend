# Build Stage - Install dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install UV (Better package manager)
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies to .venv
RUN uv sync --frozen --no-dev

# For Production Stage - Runtime environment
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Use virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chmod -R 777 /app/logs

# TODO: Fix permissions and run as non-root user later
# For now, run as root to avoid permission issues

# Expose port
EXPOSE 5000

# Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Default Command
CMD ["python", "app.py"]