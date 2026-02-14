FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including cron
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        cron \
        build-essential \
        gcc \
        g++ \
        python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY scraper.py .
COPY predictions.py .
COPY app.py .
COPY entrypoint.sh .
COPY run_scrape_and_predict.sh .

# Create necessary directories
RUN mkdir -p /app/data /app/data/predictions /app/logs

# Make scripts executable
RUN chmod +x /app/entrypoint.sh /app/run_scrape_and_predict.sh

# Expose Flask port
EXPOSE 5000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
