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
from prefect.tasks import task_input_hash
from datetime import timedelta
import lakefs

class EGATRealTimeScraper:
    def __init__(self, url="https://www.sothailand.com/sysgen/egat/"):
        self.url = url
        self.driver = self._initialize_driver()
        
    def _initialize_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # Updated headless argument
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--enable-javascript")
        chrome_options.add_argument("--enable-logging")
        chrome_options.add_argument("--v=1")  # Verbose logging
        
        # Enable Chrome DevTools Protocol for better console log capture
        chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        
        chromedriver_path = os.getenv('CHROMEDRIVER_PATH')
        service = Service(chromedriver_path if chromedriver_path and os.path.exists(chromedriver_path) else ChromeDriverManager().install())
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
        
    def extract_data_from_console(self):
        logs = self.driver.get_log('browser')
        
        # Debug log count
        print(f"Found {len(logs)} browser logs")
        
        if not logs:
            print("No console logs found. Waiting longer and trying again...")
            time.sleep(5)
            logs = self.driver.get_log('browser')
            print(f"Second attempt found {len(logs)} browser logs")
            
        for log_entry in reversed(logs):
            message = log_entry.get('message', '')
            print(f"Log entry: {message[:100]}..." if len(message) > 100 else f"Log entry: {message}")
            
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
        
        # Try an alternative approach if regex doesn't match
        print("No matching data found in console logs. Trying alternative approach...")
        try:
            # Execute JavaScript to get the values directly
            date_id = self.driver.execute_script("return document.querySelector('.messageHeader')?.innerText.trim().split(' ')[0];")
            time_str = self.driver.execute_script("return document.querySelector('.messageHeader')?.innerText.trim().split(' ')[1];")
            power = self.driver.execute_script("return document.querySelector('.messageValue')?.innerText.trim().replace(',','');")
            temp = self.driver.execute_script("return document.querySelector('.messageTemp')?.innerText.trim();")
            
            if date_id and time_str and power and temp:
                print(f"Found data using JS: date={date_id}, time={time_str}, power={power}, temp={temp}")
                return {
                    'scrape_timestamp_utc': datetime.datetime.utcnow().isoformat(),
                    'display_date_id': date_id,
                    'display_time': time_str,
                    'current_value_MW': float(power),
                    'temperature_C': float(temp)
                }
        except Exception as e:
            print(f"JS extraction failed: {str(e)}")
            
        return None
                    
    def scrape_once(self):
        self.driver.get(self.url)
        print(f"Navigating to {self.url}")
        
        # Wait longer to ensure page loads completely
        print("Waiting for page to load...")
        time.sleep(15)
        
        # Take screenshot for debugging
        try:
            screenshot_path = "page_debug.png"
            self.driver.save_screenshot(screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")
        except Exception as e:
            print(f"Failed to save screenshot: {str(e)}")
        
        data = self.extract_data_from_console()
        
        if not data:
            print("First attempt failed. Trying again with longer wait...")
            time.sleep(10)
            data = self.extract_data_from_console()
            
        return data
        
    def close(self):
        self.driver.quit()

@task(cache_key_fn=None)  # Disable caching for this task
def initialize_scraper_task(url="https://www.sothailand.com/sysgen/egat/"):
    logger = get_run_logger()
    logger.info(f"Initializing scraper for URL: {url}")
    return EGATRealTimeScraper(url=url)

@task(cache_key_fn=None)  # Disable caching for this task
def scrape_data_task(scraper):
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

@task(cache_key_fn=None)  # Disable caching for this task
def close_scraper_task(scraper):
    logger = get_run_logger()
    logger.info("Closing scraper")
    try:
        scraper.close()
    except Exception as e:
        logger.warning(f"Error closing scraper: {str(e)}")

@flow(name="EGAT Real-Time Power Data Pipeline")
def egat_data_pipeline():
    logger = get_run_logger()
    logger.info("Starting EGAT data pipeline flow")
    
    # Environment configuration
    ACCESS_KEY = os.getenv("LAKEFS_ACCESS_KEY_ID", "access_key")
    SECRET_KEY = os.getenv("LAKEFS_SECRET_ACCESS_KEY", "secret_key")
    LAKEFS_ENDPOINT = os.getenv("LAKEFS_ENDPOINT_URL", "http://localhost:8001/")
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
    
    # Execute pipeline steps with error handling
    try:
        scraper = initialize_scraper_task()
        
        # Add retry logic for scraping
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            logger.info(f"Scrape attempt {attempt} of {max_retries}")
            new_data = scrape_data_task(scraper)
            
            if new_data:
                logger.info("Data scraped successfully")
                break
            
            if attempt < max_retries:
                logger.warning(f"Scrape attempt {attempt} failed, retrying in 30 seconds...")
                time.sleep(30)
        
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
            logger.warning("No data was scraped after all attempts, pipeline completed with no updates")
    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
    finally:
        # Always try to close the scraper
        try:
            close_scraper_task(scraper)
        except Exception as e:
            logger.error(f"Error in closing scraper: {str(e)}")
        
    logger.info("EGAT data pipeline flow completed")

if __name__ == "__main__":
    egat_data_pipeline()