FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the project configuration files
COPY pyproject.toml ./
# If a uv.lock file exists, uncomment the next line
# COPY uv.lock ./

# Install uv package manager and sync dependencies from pyproject.toml
RUN pip install --no-cache-dir uv && uv sync

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV PYTHONPATH=/app

# Expose the port the app runs on
EXPOSE ${PORT}

# Run FastAPI with uvicorn
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]