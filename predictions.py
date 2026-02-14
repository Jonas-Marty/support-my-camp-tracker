#!/usr/bin/env python3
"""
Migros SupportMyCamp Voucher Predictions

Generates predictions for club voucher counts and estimated payouts using Prophet forecasting.
Processes historical hourly data to predict values through redemption deadline.
"""

import os
import glob
import json
import time
import pandas as pd
from prophet import Prophet
import logging
import concurrent.futures
from datetime import datetime
from pathlib import Path

# Suppress Prophet logging
logging.getLogger('cmdstanpy').setLevel(logging.WARNING)
logging.getLogger('prophet').setLevel(logging.WARNING)

# Setup logging
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "predictions.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION & CONSTANTS ---
DISTRIBUTION_END_DATE = "2026-04-15 23:59:59"
REDEMPTION_END_DATE = "2026-04-22 23:59:59"
FIXED_MONEY_BUCKET = 3_000_000  # CHF
DATA_DIR = Path("data")
PREDICTIONS_DIR = DATA_DIR / "predictions"

# Set to None to run all clubs, or a number to limit (useful for testing)
LIMIT_CLUBS = None

# Minimum data points required for forecasting
MIN_DATA_POINTS = 3


# --- DATA INGESTION & ZERO-FILLING ---
def load_and_parse_json(directory_path):
    """
    Load all stats_*.json files and create time-series dataframes.
    Zero-fills missing club data across all timestamps.
    """
    logger.info("Loading and parsing JSON files...")
    start_load = time.time()
    global_metadata = []
    club_data = []
    
    files = sorted(glob.glob(os.path.join(directory_path, "stats_*.json")))
    if not files:
        raise FileNotFoundError(f"No stats_*.json files found in {directory_path}")
    
    logger.info(f"Found {len(files)} data files")
        
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            content = json.load(f)
            timestamp = content["metadata"]["timestamp"]
            global_metadata.append(content["metadata"])
            
            for club in content.get("clubs", []):
                club_record = club.copy()
                club_record["timestamp"] = timestamp
                club_data.append(club_record)
    
    # Create global metadata dataframe
    df_global = pd.DataFrame(global_metadata)
    df_global['ds'] = pd.to_datetime(df_global['timestamp']).dt.tz_localize(None)
    df_global = df_global.sort_values('ds').reset_index(drop=True)
    
    # Create clubs dataframe with zero-filling
    df_clubs_raw = pd.DataFrame(club_data)
    df_clubs_raw['ds'] = pd.to_datetime(df_clubs_raw['timestamp']).dt.tz_localize(None)
    df_clubs_raw['estimatedPayout'] = df_clubs_raw['estimatedPayout'].astype(float)
    
    # Zero-fill: create grid of all timestamps × all clubs
    all_timestamps = df_global['ds'].unique()
    df_timestamps = pd.DataFrame({'ds': all_timestamps})
    
    latest_timestamp = df_global['ds'].max()
    latest_clubs = df_clubs_raw[df_clubs_raw['ds'] == latest_timestamp][['publicId', 'name']].drop_duplicates()
    df_grid = df_timestamps.merge(latest_clubs, how='cross')
    
    df_clubs = df_grid.merge(
        df_clubs_raw[['ds', 'publicId', 'voucherCount', 'estimatedPayout']], 
        on=['ds', 'publicId'], 
        how='left'
    )
    df_clubs['voucherCount'] = df_clubs['voucherCount'].fillna(0)
    df_clubs['estimatedPayout'] = df_clubs['estimatedPayout'].fillna(0)
    df_clubs = df_clubs.sort_values(['publicId', 'ds']).reset_index(drop=True)
    
    logger.info(f"Loaded {len(files)} files in {time.time() - start_load:.2f} seconds")
    logger.info(f"Global data points: {len(df_global)}, Club records: {len(df_clubs)}")
    
    return df_global, df_clubs


# --- HELPER: DYNAMIC CAP ---
def calculate_dynamic_cap(df_series, distribution_end):
    """
    Calculate dynamic capacity for logistic growth model based on current trend.
    """
    if len(df_series) < 2:
        return df_series['y'].iloc[-1] * 1.1
    
    first_val = df_series.iloc[0]
    last_val = df_series.iloc[-1]
    
    hours_passed = (last_val['ds'] - first_val['ds']).total_seconds() / 3600
    if hours_passed == 0:
        return last_val['y']
    
    rate = (last_val['y'] - first_val['y']) / hours_passed
    hours_remaining = (pd.to_datetime(distribution_end) - last_val['ds']).total_seconds() / 3600
    projected_cap = last_val['y'] + (rate * max(0, hours_remaining))
    
    return int(projected_cap * 1.05)


# --- FORECASTING FUNCTIONS ---
def get_prophet_forecast(df, target_column):
    """
    Generate Prophet forecast for a given time series.
    Enforces monotonic increase since voucher counts are cumulative.
    """
    prophet_df = df[['ds', target_column]].rename(columns={target_column: 'y'}).copy()
    
    m = Prophet(
        growth='linear',
        daily_seasonality=True,
        weekly_seasonality=True,
        seasonality_mode='additive',
        interval_width=0.95
    )
    
    # Suppress output
    import sys
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        m.fit(prophet_df)
    finally:
        sys.stdout = old_stdout
    
    last_date = prophet_df['ds'].max()
    hours_to_forecast = int((pd.to_datetime(REDEMPTION_END_DATE) - last_date).total_seconds() / 3600)
    
    if hours_to_forecast > 0:
        future = m.make_future_dataframe(periods=hours_to_forecast, freq='h')
        forecast = m.predict(future)
        
        # Enforce monotonic increase (vouchers can only go up, never down)
        # This ensures voucher worth only decreases over time
        forecast['yhat'] = forecast['yhat'].cummax()
        
        return forecast[['ds', 'yhat']]
    
    return prophet_df.rename(columns={'y': 'yhat'})


# --- WORKER FUNCTION FOR MULTIPROCESSING ---
def process_single_club(args):
    """
    Worker function executed by separate CPU core for parallel processing.
    """
    # Suppress logging in worker processes
    logging.getLogger('cmdstanpy').setLevel(logging.WARNING)
    logging.getLogger('prophet').setLevel(logging.WARNING)
    
    club_id, club_name, current_vouchers, current_payout, club_df, global_forecast_df, snapshot_dates = args
    start_time = time.time()
    
    try:
        # Check if we have enough data points
        if len(club_df) < MIN_DATA_POINTS:
            logger.warning(f"Insufficient data for {club_name} ({len(club_df)} points)")
            return None, club_name, time.time() - start_time
        
        club_forecast_df = get_prophet_forecast(club_df, 'voucherCount')
        
        merged_timeline = pd.merge(
            club_forecast_df, 
            global_forecast_df, 
            on='ds', 
            suffixes=('_club', '_global')
        )
        merged_timeline['projected_payout'] = merged_timeline['yhat_club'] * merged_timeline['predicted_worth']
        
        club_result = {
            "publicId": club_id,
            "name": club_name,
            "current_vouchers": int(current_vouchers),
            "current_payout": float(current_payout)
        }
        
        for target_date in snapshot_dates:
            closest_row = merged_timeline.iloc[(merged_timeline['ds'] - target_date).abs().argsort()[:1]]
            date_str = target_date.strftime("%Y-%m-%d")
            club_result[f"payout_by_{date_str}"] = round(closest_row['projected_payout'].values[0], 2)
            club_result[f"vouchers_by_{date_str}"] = int(closest_row['yhat_club'].values[0])
        
        duration = time.time() - start_time
        return club_result, club_name, duration
        
    except Exception as e:
        logger.error(f"Error processing {club_name}: {e}")
        return None, club_name, time.time() - start_time


# --- MAIN EXECUTION ---
def main():
    """Main prediction execution"""
    script_start_time = time.time()
    
    logger.info("=" * 80)
    logger.info("Starting SupportMyCamp Predictions")
    logger.info("=" * 80)
    
    try:
        # Ensure predictions directory exists
        PREDICTIONS_DIR.mkdir(exist_ok=True)
        
        # Load data
        df_global, df_clubs = load_and_parse_json(DATA_DIR)
        
        # Check minimum data requirements
        if len(df_global) < MIN_DATA_POINTS:
            logger.error(f"Insufficient data points ({len(df_global)}) - need at least {MIN_DATA_POINTS}")
            return
        
        # Global forecast for voucher worth
        logger.info("Generating global voucher worth timeline...")
        global_forecast_df = get_prophet_forecast(df_global, 'totalVouchers')
        global_forecast_df['predicted_worth'] = FIXED_MONEY_BUCKET / global_forecast_df['yhat']
        
        # Define snapshot dates
        latest_data_date = df_global['ds'].max()
        snapshot_dates = pd.date_range(start=latest_data_date, end=REDEMPTION_END_DATE, freq='7D')
        
        # Ensure redemption end date is included
        redemption_dt = pd.to_datetime(REDEMPTION_END_DATE)
        if redemption_dt not in snapshot_dates:
            snapshot_dates = pd.DatetimeIndex(list(snapshot_dates) + [redemption_dt])
        
        # Get clubs to process
        latest_club_data = df_clubs[df_clubs['ds'] == df_clubs['ds'].max()]
        clubs_to_process = latest_club_data.sort_values(by='voucherCount', ascending=False)
        
        if LIMIT_CLUBS:
            clubs_to_process = clubs_to_process.head(LIMIT_CLUBS)
            logger.info(f"Limited to top {LIMIT_CLUBS} clubs for testing")
        
        total_clubs = len(clubs_to_process)
        
        # Multiprocessing setup
        logical_cores = os.cpu_count() or 1
        logger.info(f"Processing {total_clubs} clubs across {logical_cores} logical cores")
        
        # Package tasks for worker pool
        tasks = []
        for _, club_info in clubs_to_process.iterrows():
            club_id = club_info['publicId']
            club_df = df_clubs[df_clubs['publicId'] == club_id].copy()
            tasks.append((
                club_id,
                club_info['name'],
                club_info['voucherCount'],
                club_info['estimatedPayout'],
                club_df,
                global_forecast_df,
                snapshot_dates
            ))
        
        results = []
        completed = 0
        
        # Execute parallel processing
        with concurrent.futures.ProcessPoolExecutor(max_workers=logical_cores) as executor:
            futures = {executor.submit(process_single_club, task): task for task in tasks}
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    club_result, club_name, duration = future.result()
                    if club_result:
                        results.append(club_result)
                    completed += 1
                    
                    # Progress logging
                    if completed % 50 == 0 or completed == total_clubs:
                        logger.info(f"Progress: {completed}/{total_clubs} clubs processed")
                    
                except Exception as exc:
                    logger.error(f"Club processing generated exception: {exc}")
        
        if not results:
            logger.error("No predictions generated")
            return
        
        # Create dataframe and sort by final payout
        final_df = pd.DataFrame(results)
        final_date_str = snapshot_dates[-1].strftime("%Y-%m-%d")
        final_df = final_df.sort_values(by=f"payout_by_{final_date_str}", ascending=False)
        
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        timestamped_file = PREDICTIONS_DIR / f"predictions_{timestamp}.csv"
        latest_file = PREDICTIONS_DIR / "predictions_latest.csv"
        
        final_df.to_csv(timestamped_file, index=False)
        logger.info(f"Saved predictions to {timestamped_file}")
        
        # Copy to latest
        final_df.to_csv(latest_file, index=False)
        logger.info(f"Updated {latest_file}")
        
        # Save global voucher worth timeline
        worth_timeline = global_forecast_df[['ds', 'yhat', 'predicted_worth']].copy()
        worth_timeline.rename(columns={'yhat': 'predicted_vouchers'}, inplace=True)
        worth_timeline['ds'] = worth_timeline['ds'].dt.strftime('%Y-%m-%d %H:%M:%S')
        worth_timeline_file = PREDICTIONS_DIR / f"voucher_worth_timeline_{timestamp}.csv"
        worth_timeline_latest_file = PREDICTIONS_DIR / "voucher_worth_timeline_latest.csv"
        
        worth_timeline.to_csv(worth_timeline_file, index=False)
        worth_timeline.to_csv(worth_timeline_latest_file, index=False)
        logger.info(f"Saved voucher worth timeline to {worth_timeline_file}")
        
        total_duration = time.time() - script_start_time
        logger.info("=" * 80)
        logger.info(f"Predictions completed successfully in {total_duration:.1f} seconds")
        logger.info(f"Processed {len(results)} clubs")
        logger.info(f"Failed: {total_clubs - len(results)} clubs")
        logger.info("=" * 80)
        
    except FileNotFoundError as e:
        logger.error(f"Data not found: {e}")
        logger.error("Run scraper first to collect data")
    except Exception as e:
        logger.exception(f"Prediction failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
