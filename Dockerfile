FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies including cron
RUN apt-get update && \
    apt-get install -y --no-install-recommends cron && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY scraper.py .
COPY app.py .
COPY entrypoint.sh .

# Create necessary directories
RUN mkdir -p /app/data /app/logs

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Expose Flask port
EXPOSE 5000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
