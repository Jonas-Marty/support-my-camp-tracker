#!/bin/bash
set -e

# Ensure Python output is unbuffered
export PYTHONUNBUFFERED=1

echo "=============================================="
echo "Migros SupportMyCamp Voucher Tracker"
echo "=============================================="

# Create necessary directories
mkdir -p /app/data /app/logs

# Check if data exists, if not run scraper
if [ ! -f /app/data/latest.json ]; then
    echo "No existing data found. Running initial scrape..."
    python -u /app/scraper.py
    echo "Initial scrape completed."
else
    echo "Existing data found at /app/data/latest.json"
fi

# Set up cron job
echo "Setting up cron job for automatic updates every 1 hour..."
echo "0 */1 * * * cd /app && /usr/local/bin/python -u /app/scraper.py >> /app/logs/cron.log 2>&1" | crontab -

# Start cron daemon
echo "Starting cron daemon..."
cron

echo "=============================================="
echo "Starting Flask web server on port 5000..."
echo "=============================================="

# Start Flask app in foreground
exec python -u /app/app.py
