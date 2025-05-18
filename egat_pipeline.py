import time
import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
import re
from prefect import task, flow, get_run_logger

class EGATRealTimeScraper:
    def __init__(self, url="https://www.sothailand.com/sysgen/egat/"):
        self.url = url
        self.driver = self._initialize_driver()

    def _initialize_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chromedriver_path = os.getenv('CHROMEDRIVER_PATH')
        service = Service(chromedriver_path if chromedriver_path and os.path.exists(chromedriver_path) else ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)

    def extract_data_from_console(self):
        logs = self.driver.get_log('browser')
        for log_entry in reversed(logs):
            message = log_entry.get('message', '')
            if 'updateMessageArea:' in message:
                match = re.search(r'updateMessageArea:\s*(\d+)\s*,\s*(\d{1,2}:\d{2})\s*,\s*([\d,]+\.?\d*)\s*,\s*(\d*\.?\d+)', message)
                if match:
                    current_value_mw = float(match.group(3).replace(',', '').strip())
                    temperature_c = float(match.group(4).strip())
                    return {
                        'scrape_timestamp_utc': datetime.datetime.utcnow().isoformat(),
                        'display_date_id': match.group(1).strip(),
                        'display_time': match.group(2).strip(),
                        'current_value_MW': current_value_mw,
                        'temperature_C': temperature_c
                    }

    def scrape_once(self):
        self.driver.get(self.url)
        time.sleep(10)
        return self.extract_data_from_console()

    def close(self):
        self.driver.quit()

@task
def initialize_scraper_task(url="https://www.sothailand.com/sysgen/egat/"):
    return EGATRealTimeScraper(url=url)

@task
def scrape_data_task(scraper: EGATRealTimeScraper):
    return scraper.scrape_once()

@task
def process_and_store_data_task(new_data_dict: dict, lakefs_s3_path: str, storage_options: dict):
    existing_df = pd.DataFrame()
    try:
        existing_df = pd.read_parquet(lakefs_s3_path, storage_options=storage_options)
        existing_df['scrape_timestamp_utc'] = pd.to_datetime(existing_df['scrape_timestamp_utc'], errors='coerce').dt.tz_localize(None)
    except:
        pass
    new_df = pd.DataFrame([new_data_dict])
    new_df['scrape_timestamp_utc'] = pd.to_datetime(new_df['scrape_timestamp_utc'], errors='coerce').dt.tz_localize(None)
    combined_df = pd.concat([existing_df, new_df], ignore_index=True) if not existing_df.empty else new_df
    combined_df.sort_values('scrape_timestamp_utc', ascending=True, inplace=True, na_position='last')
    combined_df.drop_duplicates(subset=['display_date_id', 'display_time'], keep='first', inplace=True)
    combined_df['scrape_timestamp_utc'] = combined_df['scrape_timestamp_utc'].astype(str)
    combined_df.to_parquet(lakefs_s3_path, storage_options=storage_options, index=False, engine='pyarrow', compression='snappy')

@task
def close_scraper_task(scraper: EGATRealTimeScraper):
    scraper.close()

@flow
def egat_data_pipeline():
    ACCESS_KEY = os.getenv("LAKEFS_ACCESS_KEY_ID", "access_key")
    SECRET_KEY = os.getenv("LAKEFS_SECRET_ACCESS_KEY", "secret_key")
    LAKEFS_ENDPOINT = os.getenv("LAKEFS_ENDPOINT_URL", "http://lakefs-dev:8000/")
    REPO_NAME = "dataset"
    BRANCH_NAME = "main"
    TARGET_PARQUET_FILE_PATH = "egat_datascraping/egat_realtime_power_history.parquet"
    lakefs_s3_path = f"s3a://{REPO_NAME}/{BRANCH_NAME}/{TARGET_PARQUET_FILE_PATH}"
    storage_options = {
        "key": ACCESS_KEY,
        "secret": SECRET_KEY,
        "client_kwargs": {
            "endpoint_url": LAKEFS_ENDPOINT
        }
    }

    scraper = initialize_scraper_task()
    new_data = scrape_data_task(scraper)
    if new_data:
        process_and_store_data_task(new_data, lakefs_s3_path, storage_options)
    close_scraper_task(scraper)

if __name__ == "__main__":
    egat_data_pipeline()