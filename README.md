# Migros SupportMyCamp Voucher Tracker

A web application that tracks and displays voucher statistics for clubs participating in the Migros SupportMyCamp campaign. The application scrapes data from the SupportMyCamp API and presents it in a mobile-optimized web interface.

## Features

- 🔄 Automated data scraping every 2 hours
- 📱 Mobile-optimized responsive web interface
- 🔍 Real-time search functionality with debouncing
- 📊 Display of voucher counts and estimated payouts
- 🔒 File-based locking to prevent concurrent scrapes
- 🔁 Retry logic with incremental backoff
- 📝 Comprehensive logging
- 🐳 Docker containerized for easy deployment

## Quick Start with Docker

1. **Build and run the container:**
   ```bash
   docker-compose up -d
   ```

2. **Access the web interface:**
   Open your browser and navigate to `http://localhost:5000`

## Manual Setup

### Prerequisites

- Python 3.14+
- pip

### Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the scraper manually:**
   ```bash
   python scraper.py
   ```

3. **Start the web server:**
   ```bash
   python app.py
   ```

4. **Access the application:**
   Navigate to `http://localhost:5000` in your browser

## Project Structure

```
SupportMyCampScrapper/
├── app.py              # Flask web application
├── scraper.py          # Data scraper with API integration
├── entrypoint.sh       # Docker startup script
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker image configuration
├── docker-compose.yml  # Docker Compose configuration
├── data/               # Data storage directory
│   └── latest.json     # Current voucher statistics
└── logs/               # Log files directory
    ├── scraper.log     # Scraper execution logs
    └── cron.log        # Cron job logs
```

## Configuration

### Scraper Settings

Edit `scraper.py` to modify:
- `PAGE_SIZE`: Number of clubs per API request (default: 100, max: 100)
- `RATE_LIMIT_DELAY`: Delay between requests in seconds (default: 0.05)
- `RETRY_ATTEMPTS`: Number of retry attempts (default: 3)
- `LOCK_TIMEOUT`: Lock timeout in seconds (default: 600)

### Cron Schedule

The default cron schedule is every 2 hours. To modify, edit the cron entry in `entrypoint.sh`:
```bash
# Current: Every 2 hours
0 */2 * * *

# Examples:
# Every hour: 0 * * * *
# Every 4 hours: 0 */4 * * *
# Daily at 2 AM: 0 2 * * *
```

## Data Structure

### latest.json Format

```json
{
  "metadata": {
    "timestamp": "2026-02-10T12:00:00",
    "totalClubs": 2172,
    "totalVouchers": 500000,
    "voucherWorth": 6.00
  },
  "clubs": [
    {
      "publicId": "uuid",
      "name": "Club Name",
      "leaderboardRank": 1,
      "fanCount": 100,
      "donationSum": "1000.00",
      "voucherCount": 500,
      "estimatedPayout": 3000.00
    }
  ]
}
```

## Logging

- **scraper.log**: Contains detailed scraper execution logs including progress, errors, and statistics
- **cron.log**: Contains output from scheduled cron executions

View logs in real-time:
```bash
# Scraper logs
docker-compose exec app tail -f /app/logs/scraper.log

# Cron logs
docker-compose exec app tail -f /app/logs/cron.log
```

## Troubleshooting

### No data displayed on website
- Check if `data/latest.json` exists
- Review `logs/scraper.log` for errors
- Run scraper manually: `docker-compose exec app python /app/scraper.py`

### Scraper not running automatically
- Check cron status: `docker-compose exec app crontab -l`
- Review cron logs: `docker-compose exec app cat /app/logs/cron.log`

### Lock file preventing execution
- The lock file automatically expires after 10 minutes
- Manual removal: `docker-compose exec app rm /app/data/.scraper.lock`

## License

This project is for educational and informational purposes only.

## API Information

This scraper uses the public Migros SupportMyCamp API:
- Base URL: `https://supportmycamp.migros.ch/api/v1/frontend`
- No authentication required for public endpoints
- Rate limiting: 50ms between requests (configurable)
