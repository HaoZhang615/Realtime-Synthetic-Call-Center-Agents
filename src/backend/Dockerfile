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
ENV PORT=80
ENV PYTHONPATH=/app

# Ensure directories are treated as packages and verify structure
RUN touch __init__.py pages/__init__.py utils/__init__.py && \
    ls -la /app && \
    ls -la /app/utils && \
    echo "PYTHONPATH: $PYTHONPATH" && \
    python -c "import sys; print('Python path:', sys.path)"

# Expose the port the app runs on
EXPOSE ${PORT}

# Wrap the startup command to print debug info
CMD echo "Current directory: $(pwd)" && \
    echo "Directory contents: $(ls -la)" && \
    echo "Python path: $(python -c 'import sys; print(sys.path)')" && \
    /app/.venv/bin/streamlit run Admin.py --server.port=80 --server.address=0.0.0.0 --server.enableCORS false