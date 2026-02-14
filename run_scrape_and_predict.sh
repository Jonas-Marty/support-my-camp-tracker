#!/bin/bash
# Automated scraping and prediction script
# Runs scraper first, then generates predictions if scrape succeeds

set -e

echo "=========================================="
echo "$(date): Starting automated update"
echo "=========================================="

# Run scraper
echo "Running scraper..."
/usr/local/bin/python -u /app/scraper.py

SCRAPER_EXIT=$?
if [ $SCRAPER_EXIT -ne 0 ]; then
    echo "ERROR: Scraper failed with exit code $SCRAPER_EXIT"
    exit $SCRAPER_EXIT
fi

echo "Scraper completed successfully"

# Run predictions
echo "Running predictions..."
/usr/local/bin/python -u /app/predictions.py

PREDICTIONS_EXIT=$?
if [ $PREDICTIONS_EXIT -ne 0 ]; then
    echo "WARNING: Predictions failed with exit code $PREDICTIONS_EXIT"
    # Don't exit with error - predictions may fail if insufficient data
fi

echo "=========================================="
echo "$(date): Automated update completed"
echo "=========================================="
