#!/usr/bin/env python3
"""
Migros SupportMyCamp Voucher Scraper

Fetches all participating clubs and their voucher statistics from the SupportMyCamp API.
Includes rate limiting, retry logic with incremental backoff, and file-based locking.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Configuration
BASE_URL = "https://supportmycamp.migros.ch/api/v1/frontend"
CLUBS_ENDPOINT = f"{BASE_URL}/organisation-search-public/"
STATS_ENDPOINT_TEMPLATE = f"{BASE_URL}/organisation-public/{{public_id}}/stats/"
PAGE_SIZE = 100
RATE_LIMIT_DELAY = 0.02  # 20ms between requests
RETRY_ATTEMPTS = 3
RETRY_DELAYS = [0.1, 0.2, 0.4]  # Incremental backoff: 100ms, 200ms, 400ms
LOCK_TIMEOUT = 600  # 10 minutes in seconds
TOTAL_PRIZE_POOL = 3_000_000.0  # CHF
DATA_DIR = Path("data")
LOGS_DIR = Path("logs")
LOCK_FILE = DATA_DIR / ".scraper.lock"

# Headers to mimic a real browser and avoid 403 errors
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'de-CH,de;q=0.9,en;q=0.8',
    'Referer': 'https://supportmycamp.migros.ch/',
    'Origin': 'https://supportmycamp.migros.ch',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}

# Setup logging
LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ScraperLockError(Exception):
    """Raised when unable to acquire scraper lock"""
    pass


class ScraperLock:
    """File-based lock with timeout for preventing concurrent scraper runs"""
    
    def __init__(self, lock_file: Path, timeout: int = LOCK_TIMEOUT):
        self.lock_file = lock_file
        self.timeout = timeout
        self.acquired = False
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
    
    def acquire(self):
        """Acquire the lock, checking for stale locks"""
        if self.lock_file.exists():
            # Check if lock is stale
            lock_age = time.time() - self.lock_file.stat().st_mtime
            if lock_age < self.timeout:
                raise ScraperLockError(
                    f"Another scraper instance is running (lock age: {lock_age:.1f}s)"
                )
            else:
                logger.warning(
                    f"Removing stale lock file (age: {lock_age:.1f}s, timeout: {self.timeout}s)"
                )
                self.lock_file.unlink()
        
        # Create lock file
        self.lock_file.parent.mkdir(exist_ok=True)
        self.lock_file.write_text(str(os.getpid()))
        self.acquired = True
        logger.info("Lock acquired successfully")
    
    def release(self):
        """Release the lock"""
        if self.acquired and self.lock_file.exists():
            self.lock_file.unlink()
            self.acquired = False
            logger.info("Lock released")


def make_request_with_retry(url: str, retry_count: int = RETRY_ATTEMPTS) -> Optional[Dict]:
    """
    Make HTTP GET request with retry logic and incremental backoff
    
    Args:
        url: URL to fetch
        retry_count: Number of retry attempts
    
    Returns:
        JSON response as dict or None if all retries failed
    """
    for attempt in range(retry_count):
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
            response.raise_for_status()
            
            # Check if response has content
            if not response.content:
                raise ValueError("Empty response body")
            
            return response.json()
        except requests.exceptions.HTTPError as e:
            # HTTP error with status code
            status_code = e.response.status_code if e.response else "unknown"
            if attempt < retry_count - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(
                    f"HTTP {status_code} error (attempt {attempt + 1}/{retry_count}): {e}\n"
                    f"URL: {url}\n"
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"HTTP {status_code} error after {retry_count} attempts: {e}\n"
                    f"URL: {url}"
                )
                return None
        except json.JSONDecodeError as e:
            # JSON decode error - log response content for debugging
            response_preview = response.text[:200] if hasattr(response, 'text') else "N/A"
            content_type = response.headers.get('Content-Type', 'unknown') if hasattr(response, 'headers') else "N/A"
            
            if attempt < retry_count - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(
                    f"JSON decode error (attempt {attempt + 1}/{retry_count}): {e}\n"
                    f"URL: {url}\n"
                    f"Content-Type: {content_type}\n"
                    f"Response preview: {response_preview}\n"
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"JSON decode error after {retry_count} attempts: {e}\n"
                    f"URL: {url}\n"
                    f"Content-Type: {content_type}\n"
                    f"Response body: {response.text if hasattr(response, 'text') else 'N/A'}"
                )
                return None
        except (requests.exceptions.RequestException, ValueError) as e:
            # Other errors (connection, timeout, empty response, etc.)
            if attempt < retry_count - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{retry_count}): {e}\n"
                    f"URL: {url}\n"
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"Request failed after {retry_count} attempts: {e}\n"
                    f"URL: {url}"
                )
                return None
    
    return None


def fetch_clubs_with_params(ordering: str = None, age_group: str = None) -> set:
    """
    Fetch clubs with specific ordering and age group parameters
    
    Args:
        ordering: Ordering parameter (e.g., 'voucher_count', '-name')
        age_group: Age group filter (e.g., '0_5', '6_11', '12_15', '16_99')
    
    Returns:
        Set of tuples (publicId, name)
    """
    clubs_set = set()
    cursor = None
    page = 1
    last_cursor = None
    
    # Build base params
    params_str = f"page_size={PAGE_SIZE}"
    if ordering:
        params_str += f"&ordering={ordering}"
    if age_group:
        params_str += f"&camp_age_groups={age_group}"
    
    logger.info(f"Fetching clubs with params: {params_str}")
    
    total_count = None
    
    while True:
        # Build URL with pagination
        if cursor:
            url = f"{CLUBS_ENDPOINT}?cursor={cursor}&{params_str}"
        else:
            url = f"{CLUBS_ENDPOINT}?{params_str}"
        
        data = make_request_with_retry(url)
        
        if not data or "results" not in data:
            logger.warning(f"Failed to fetch page {page} with params: {params_str}")
            break
        
        # Extract total count from first response
        if total_count is None and "totalCount" in data:
            total_count = data["totalCount"]
            logger.info(f"  Total count for this query: {total_count}")
        
        results = data["results"]
        
        # If no results, we've reached the end
        if not results or len(results) == 0:
            logger.info(f"  No more results at page {page}")
            break
        
        # Extract publicId and name from each club
        new_clubs = 0
        for club in results:
            if "publicId" in club and "name" in club:
                club_tuple = (club["publicId"], club["name"])
                if club_tuple not in clubs_set:
                    clubs_set.add(club_tuple)
                    new_clubs += 1
        
        logger.info(f"  Page {page}: Found {len(results)} clubs ({new_clubs} new, {len(clubs_set)} total unique)")
        
        # Check if we've reached the total count for this query
        if total_count is not None and len(clubs_set) >= total_count:
            logger.info(f"  Reached total count ({total_count}) at page {page}")
            break
        
        # Get next cursor
        cursor = data.get("next")
        
        # If no cursor, we've reached the end
        if not cursor:
            logger.info(f"  Completed fetch at page {page} - no more pages")
            break
        
        # Detect if cursor hasn't changed - parameter combination exhausted
        if cursor == last_cursor:
            logger.info(f"  Cursor unchanged at page {page} - parameter combination exhausted")
            break
        
        last_cursor = cursor
        page += 1
        time.sleep(RATE_LIMIT_DELAY)
    
    return clubs_set


def fetch_all_clubs() -> List[Dict]:
    """
    Fetch all clubs by using multiple ordering and age group combinations
    to work around API pagination limitations
    
    Returns:
        List of club dictionaries with publicId and name
    """
    logger.info("Starting to fetch club list using multiple strategies...")
    
    all_clubs = set()
    expected_total = None
    
    # Strategy 1: Different orderings
    orderings = [
        None,  # Default ordering
        "voucher_count",
        "-voucher_count",
        "member_count",
        "-member_count",
        "name",
        "-name"
    ]
    
    for ordering in orderings:
        order_name = ordering if ordering else "default"
        logger.info(f"Fetching with ordering: {order_name}")
        clubs = fetch_clubs_with_params(ordering=ordering)
        all_clubs.update(clubs)
        logger.info(f"Total unique clubs so far: {len(all_clubs)}")
        
        # Set expected total from first successful fetch
        if expected_total is None and len(clubs) > 0:
            # Get total count from API for reference
            url = f"{CLUBS_ENDPOINT}?page_size={PAGE_SIZE}"
            if ordering:
                url += f"&ordering={ordering}"
            data = make_request_with_retry(url)
            if data and "totalCount" in data:
                expected_total = data["totalCount"]
                logger.info(f"Expected total clubs from API: {expected_total}")
        
        # Check if we've collected all clubs
        if expected_total is not None and len(all_clubs) >= expected_total:
            logger.info(f"Reached expected total ({expected_total}). Stopping early.")
            break
    
    # Strategy 2: Age groups with different orderings (only if we haven't reached total yet)
    if expected_total is None or len(all_clubs) < expected_total:
        age_groups = ["0_5", "6_11", "12_15", "16_99"]
        
        for age_group in age_groups:
            logger.info(f"Fetching age group: {age_group}")
            
            # Try each age group with a few key orderings
            for ordering in [None, "voucher_count", "-voucher_count"]:
                clubs = fetch_clubs_with_params(ordering=ordering, age_group=age_group)
                all_clubs.update(clubs)
                
                # Check if we've reached the expected total
                if expected_total is not None and len(all_clubs) >= expected_total:
                    logger.info(f"Reached expected total ({expected_total}) in age group {age_group}. Stopping early.")
                    break
            
            logger.info(f"Total unique clubs after age group {age_group}: {len(all_clubs)}")
            
            # Check after each age group
            if expected_total is not None and len(all_clubs) >= expected_total:
                break
    
    # Convert set of tuples back to list of dicts
    clubs_list = [
        {"publicId": public_id, "name": name}
        for public_id, name in all_clubs
    ]
    
    logger.info("=" * 60)
    logger.info(f"Completed fetching club list. Total unique clubs: {len(clubs_list)}")
    if expected_total:
        logger.info(f"Expected: {expected_total}, Found: {len(clubs_list)} ({len(clubs_list)/expected_total*100:.1f}%)")
    logger.info("=" * 60)
    
    return clubs_list


def fetch_club_stats(public_id: str, club_name: str) -> Optional[Dict]:
    """
    Fetch statistics for a single club
    
    Args:
        public_id: Club's public ID (GUID)
        club_name: Club's name (for logging)
    
    Returns:
        Club stats dictionary or None if failed
    """
    url = STATS_ENDPOINT_TEMPLATE.format(public_id=public_id)
    data = make_request_with_retry(url)
    
    if not data:
        logger.error(f"Failed to fetch stats for club: {club_name} (ID: {public_id})")
        return None
    
    # Validate required fields
    if "voucherCount" not in data:
        logger.error(f"Invalid stats response for club {club_name}: missing voucherCount")
        return None
    
    return data


def fetch_all_club_stats(clubs: List[Dict]) -> List[Dict]:
    """
    Fetch statistics for all clubs with rate limiting and progress logging
    
    Args:
        clubs: List of clubs with publicId and name
    
    Returns:
        List of club dictionaries with complete stats (excluding failed clubs)
    """
    total_clubs = len(clubs)
    all_stats = []
    failed_clubs = []
    
    logger.info(f"Starting to fetch stats for {total_clubs} clubs...")
    
    for idx, club in enumerate(clubs, 1):
        public_id = club["publicId"]
        club_name = club["name"]
        
        # Progress logging every 100 clubs
        if idx % 100 == 0 or idx == total_clubs:
            logger.info(f"Fetching club stats: {idx}/{total_clubs} ({len(all_stats)} successful, {len(failed_clubs)} failed)")
        
        stats = fetch_club_stats(public_id, club_name)
        
        if stats is None:
            logger.warning(f"Skipping club {club_name} due to fetch failure")
            failed_clubs.append(club_name)
            # Continue with next club instead of aborting
            if idx < total_clubs:
                time.sleep(RATE_LIMIT_DELAY)
            continue
        
        # Combine club info with stats
        club_data = {
            "publicId": public_id,
            "name": club_name,
            "leaderboardRank": stats.get("leaderboardRank"),
            "fanCount": stats.get("fanCount"),
            "donationSum": stats.get("donationSum"),
            "voucherCount": stats.get("voucherCount", 0)
        }
        
        all_stats.append(club_data)
        
        # Rate limiting
        if idx < total_clubs:
            time.sleep(RATE_LIMIT_DELAY)
    
    if failed_clubs:
        logger.warning(f"Failed to fetch stats for {len(failed_clubs)} clubs: {', '.join(failed_clubs[:10])}{'...' if len(failed_clubs) > 10 else ''}")
    
    logger.info(f"Successfully fetched stats for {len(all_stats)} out of {total_clubs} clubs")
    return all_stats


def calculate_payouts(clubs_stats: List[Dict]) -> tuple[List[Dict], Dict]:
    """
    Calculate estimated payouts for each club based on voucher distribution
    
    Args:
        clubs_stats: List of club statistics
    
    Returns:
        Tuple of (clubs with payouts, metadata dict)
    """
    total_vouchers = sum(club["voucherCount"] for club in clubs_stats)
    
    if total_vouchers == 0:
        logger.warning("Total vouchers is 0, cannot calculate payouts")
        voucher_worth = 0.0
    else:
        voucher_worth = round(TOTAL_PRIZE_POOL / total_vouchers, 2)
    
    logger.info(f"Total vouchers: {total_vouchers:,}")
    logger.info(f"Voucher worth: CHF {voucher_worth:.2f}")
    
    # Calculate payout for each club
    for club in clubs_stats:
        estimated_payout = round(club["voucherCount"] * voucher_worth, 2)
        club["estimatedPayout"] = estimated_payout
    
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "totalClubs": len(clubs_stats),
        "totalVouchers": total_vouchers,
        "voucherWorth": voucher_worth
    }
    
    return clubs_stats, metadata


def save_data(clubs_with_payouts: List[Dict], metadata: Dict):
    """
    Save scraped data to timestamped file and update latest.json
    
    Args:
        clubs_with_payouts: List of clubs with calculated payouts
        metadata: Metadata dictionary
    """
    DATA_DIR.mkdir(exist_ok=True)
    
    # Create timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    timestamped_file = DATA_DIR / f"stats_{timestamp}.json"
    latest_file = DATA_DIR / "latest.json"
    
    # Prepare data structure
    output_data = {
        "metadata": metadata,
        "clubs": clubs_with_payouts
    }
    
    # Write timestamped file
    with open(timestamped_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved data to {timestamped_file}")
    
    # Copy to latest.json
    with open(latest_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Updated {latest_file}")


def main():
    """Main scraper execution"""
    start_time = time.time()
    logger.info("=" * 80)
    logger.info("Starting Migros SupportMyCamp scraper")
    logger.info("=" * 80)
    
    try:
        # Acquire lock to prevent concurrent runs
        with ScraperLock(LOCK_FILE):
            # Step 1: Fetch all clubs
            clubs = fetch_all_clubs()
            
            if not clubs:
                logger.error("No clubs found, aborting")
                return
            
            # Step 2: Fetch stats for all clubs
            clubs_stats = fetch_all_club_stats(clubs)
            
            # Step 3: Calculate payouts
            clubs_with_payouts, metadata = calculate_payouts(clubs_stats)
            
            # Step 4: Save data
            save_data(clubs_with_payouts, metadata)
            
            elapsed_time = time.time() - start_time
            logger.info("=" * 80)
            logger.info(f"Scraper completed successfully in {elapsed_time:.1f} seconds")
            logger.info(f"Total clubs: {metadata['totalClubs']:,}")
            logger.info(f"Total vouchers: {metadata['totalVouchers']:,}")
            logger.info(f"Voucher worth: CHF {metadata['voucherWorth']:.2f}")
            logger.info("=" * 80)
    
    except ScraperLockError as e:
        logger.error(f"Lock error: {e}")
        return
    except Exception as e:
        logger.exception(f"Scraper failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
