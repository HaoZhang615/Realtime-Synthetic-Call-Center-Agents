FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=3000

# Make sure pages directory is treated as a package
RUN touch pages/__init__.py

# Expose the port the app runs on
EXPOSE 3000

# Command to run the application
CMD ["streamlit", "run", "pages/01_Ingest_Documents.py", "--server.port", "3000", "--server.address", "0.0.0.0"]