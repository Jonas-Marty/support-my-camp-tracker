# Migros SupportMyCamp Voucher Tracker

A web application that tracks and displays voucher statistics for clubs participating in the Migros SupportMyCamp campaign. The application scrapes data from the SupportMyCamp API and presents it in a mobile-optimized web interface.

## Features

- 🔄 Automated data scraping every 1 hour
- 📈 Machine learning predictions using Prophet forecasting
- 📱 Mobile-optimized responsive web interface
- 🔍 Real-time search functionality with debouncing
- 📊 Display of voucher counts and estimated payouts
- 🔮 Predicted future payouts through redemption deadline
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

3. **Generate predictions (requires historical data):**
   ```bash
   python predictions.py
   ```

4. **Start the web server:**
   ```bash
   python app.py
   ```

5. **Access the application:**
   Navigate to `http://localhost:5000` in your browser

## Project Structure
predictions.py      # Prophet-based forecasting
├── entrypoint.sh       # Docker startup script
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker image configuration
├── docker-compose.yml  # Docker Compose configuration
├── data/               # Data storage directory
│   ├── latest.json     # Current voucher statistics
│   ├── stats_*.json    # Historical data files (timestamped)
│   └── predictions/    # Prediction results
│       ├── predictions_latest.csv              # Latest predictions
│       ├── predictions_*.csv                    # Historical predictions
│       ├── voucher_worth_timeline_latest.csv   # Latest worth timeline
│       └── voucher_worth_timeline_*.csv         # Historical timelines
└── logs/               # Log files directory
    ├── scraper.log     # Scraper execution logs
    ├── predictions.log # Predictionsimage configuration
├── docker-compose.yml  # Docker Compose configuration
├── data/               # Data storage directory
│   └── latest.json     # Current voucher statistics
└── logs/               # Log files directory
    ├── scraper.log     # Scraper execution logs
    └── cron.log        # Cron job logs
```
1 hour. To modify, edit the cron entry in `entrypoint.sh`:
```bash
# Current: Every 1 hour (scraper + predictions)
0 * * * *

# Examples:
# Every 2 hours: 0 */2 * * *
# Every 4 hours: 0 */4 * * *
# Daily at 2 AM: 0 2 * * *
```

### Predictions Settings

Edit `predictions.py` to modify:
- `DISTRIBUTION_END_DATE`: When voucher distribution ends (default: 2026-04-15)
- `REDEMPTION_END_DATE`: Final redemption deadline (default: 2026-04-22)
- `MIN_DATA_POINTS`: Minimum historical data points required (default: 3)
- `LIMIT_CLUBS`: Limit clubs for testing (default: None = all clubs)
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


### Predictions CSV Format

#### predictions_latest.csv

```csv
publicId,name,current_vouchers,current_payout,payout_by_2026-02-11,vouchers_by_2026-02-11,...,payout_by_2026-04-22,vouchers_by_2026-04-22
uuid,Club Name,500,3000.00,3150.00,525,...,3500.00,583
```Detailed scraper execution logs including progress, errors, and statistics
- **predictions.log**: Prediction generation logs, processing status, and errors
- **cron.log**: Output from scheduled cron executions

View logs in real-time:
```bash
# Scraper logs
docker-compose exec app tail -f /app/logs/scraper.log

# Predictions logs
docker-compose exec app tail -f /app/logs/predictions.log

# Cron logs
docker-compose exec app tail -f /app/logs/cron.log
```

## Manual Commands

Run commands manually inside the Docker container:

**Note for Windows Git Bash users:** Prefix paths with `//` or use PowerShell/CMD to avoid path conversion issues.

```bash
# Run scraper
docker-compose exec app python //app//scraper.py
# Or in PowerShell/CMD:
# docker-compose exec app python /app/scraper.py

# Generate predictions (requires historical data)
docker-compose exec app python //app//predictions.py

# Run both scraper and predictions (complete update)
docker-compose exec app //app//run_scrape_and_predict.sh

# View latest predictions
docker-compose exec app head -20 //app//data//predictions//predictions_latest.csv
```

## Troubleshooting

### No data displayed on website
- Check if `data/latest.json` exists
- Review `logs/scraper.log` for errors
- Run scraper manually: `docker-compose exec app python /app/scraper.py`

### Predictions not generating
- Ensure at least 3 historical data points exist (scraper must run multiple times)
- Check `logs/predictions.log` for errors
- Run predictions manually: `docker-compose exec app python /app/predictions.py`
- Verify `data/stats_*.json` files exist

### Scraper not running automatically
- Check cron status: `docker-compose exec app crontab -l`
- Review cron logs: `docker-compose exec app cat /app/logs/cron.log`

### Lock file preventing execution
- The lock file automatically expires after 10 minutes
- Manual removal: `docker-compose exec app rm /app/data/.scraper.lock`

### Prophet forecasting errors
- Ensure sufficient historical data (minimum 3 data points)
- Check system resources (Prophet is CPU-intensive)
- Review predictions.log for specific error messages

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

## License

This project is for educational and informational purposes only.

## API Information

This scraper uses the public Migros SupportMyCamp API:
- Base URL: `https://supportmycamp.migros.ch/api/v1/frontend`
- No authentication required for public endpoints
- Rate limiting: 20ms between requests (configurable)
