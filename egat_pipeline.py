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
import lakefs

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
    logger = get_run_logger()
    logger.info(f"Initializing scraper for URL: {url}")
    return EGATRealTimeScraper(url=url)

@task
def scrape_data_task(scraper: EGATRealTimeScraper):
    logger = get_run_logger()
    logger.info("Starting data scraping")
    data = scraper.scrape_once()
    if data:
        logger.info(f"Successfully scraped data: {data}")
    else:
        logger.warning("No data was scraped")
    return data

@task
def process_and_store_data_task(new_data_dict: dict, lakefs_s3_path: str, storage_options: dict):
    logger = get_run_logger()
    
    if not new_data_dict:
        logger.error("No data to process and store")
        return False
    
    logger.info(f"Processing new data: {new_data_dict}")
    logger.info(f"Target path: {lakefs_s3_path}")
    
    existing_df = pd.DataFrame()
    try:
        logger.info("Attempting to read existing data from LakeFS")
        existing_df = pd.read_parquet(lakefs_s3_path, storage_options=storage_options)
        existing_df['scrape_timestamp_utc'] = pd.to_datetime(existing_df['scrape_timestamp_utc'], errors='coerce').dt.tz_localize(None)
        logger.info(f"Successfully read existing data with {len(existing_df)} records")
    except Exception as e:
        logger.warning(f"Could not read existing data: {str(e)}")
        pass
    
    logger.info("Creating DataFrame from new data")
    new_df = pd.DataFrame([new_data_dict])
    new_df['scrape_timestamp_utc'] = pd.to_datetime(new_df['scrape_timestamp_utc'], errors='coerce').dt.tz_localize(None)
    
    logger.info("Combining existing and new data")
    combined_df = pd.concat([existing_df, new_df], ignore_index=True) if not existing_df.empty else new_df
    combined_df.sort_values('scrape_timestamp_utc', ascending=True, inplace=True, na_position='last')
    combined_df.drop_duplicates(subset=['display_date_id', 'display_time'], keep='first', inplace=True)
    
    logger.info(f"Final dataset has {len(combined_df)} records")
    combined_df['scrape_timestamp_utc'] = combined_df['scrape_timestamp_utc'].astype(str)
    
    try:
        logger.info("Writing data to LakeFS")
        combined_df.to_parquet(lakefs_s3_path, storage_options=storage_options, index=False, engine='pyarrow', compression='snappy')
        logger.info("Successfully saved data to LakeFS")
        return True
    except Exception as e:
        logger.error(f"Failed to save data to LakeFS: {str(e)}")
        return False

@task
def commit_to_lakefs_task(repo_name: str, branch_name: str, access_key: str, secret_key: str, endpoint_url: str):
    logger = get_run_logger()
    try:
        # Initialize LakeFS client
        logger.info(f"Initializing LakeFS client for repository {repo_name}")
        client = lakefs.client.Client(
            endpoint=endpoint_url,
            access_key=access_key,
            secret_key=secret_key
        )
        
        # Commit the changes
        commit_message = f"Automatic commit of EGAT data at {datetime.datetime.utcnow().isoformat()}"
        logger.info(f"Committing changes to {repo_name}/{branch_name}: {commit_message}")
        
        response = client.commit(
            repository=repo_name,
            branch=branch_name,
            message=commit_message,
            metadata={"source": "prefect_pipeline", "timestamp": datetime.datetime.utcnow().isoformat()}
        )
        
        logger.info(f"Successfully committed changes. Commit ID: {response.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to commit changes to LakeFS: {str(e)}")
        return False

@task
def close_scraper_task(scraper: EGATRealTimeScraper):
    logger = get_run_logger()
    logger.info("Closing scraper")
    scraper.close()

@flow(name="EGAT Real-Time Power Data Pipeline")
def egat_data_pipeline():
    logger = get_run_logger()
    logger.info("Starting EGAT data pipeline flow")
    
    # Environment configuration
    ACCESS_KEY = os.getenv("LAKEFS_ACCESS_KEY_ID", "access_key")
    SECRET_KEY = os.getenv("LAKEFS_SECRET_ACCESS_KEY", "secret_key")
    LAKEFS_ENDPOINT = os.getenv("LAKEFS_ENDPOINT_URL", "http://lakefs-dev:8000/")
    REPO_NAME = "dataset"
    BRANCH_NAME = "main"
    TARGET_PARQUET_FILE_PATH = "egat_datascraping/egat_realtime_power_history.parquet"
    
    logger.info(f"LakeFS configuration: Endpoint={LAKEFS_ENDPOINT}, Repo={REPO_NAME}, Branch={BRANCH_NAME}")
    
    lakefs_s3_path = f"s3a://{REPO_NAME}/{BRANCH_NAME}/{TARGET_PARQUET_FILE_PATH}"
    storage_options = {
        "key": ACCESS_KEY,
        "secret": SECRET_KEY,
        "client_kwargs": {
            "endpoint_url": LAKEFS_ENDPOINT
        }
    }
    
    # Execute pipeline steps
    scraper = initialize_scraper_task()
    new_data = scrape_data_task(scraper)
    
    if new_data:
        storage_success = process_and_store_data_task(new_data, lakefs_s3_path, storage_options)
        
        if storage_success:
            # Explicitly commit changes to LakeFS after storing the data
            commit_success = commit_to_lakefs_task(
                repo_name=REPO_NAME,
                branch_name=BRANCH_NAME,
                access_key=ACCESS_KEY,
                secret_key=SECRET_KEY,
                endpoint_url=LAKEFS_ENDPOINT
            )
            
            if commit_success:
                logger.info("Data pipeline completed successfully with commit")
            else:
                logger.error("Failed to commit changes to LakeFS")
        else:
            logger.error("Failed to store data in LakeFS")
    else:
        logger.warning("No data was scraped, pipeline completed with no updates")
    
    close_scraper_task(scraper)
    logger.info("EGAT data pipeline flow completed")

if __name__ == "__main__":
    egat_data_pipeline()