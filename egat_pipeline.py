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
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--enable-javascript")
        chrome_options.add_argument("--enable-logging")
        chrome_options.add_argument("--v=1")
        chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        chromedriver_path = os.getenv("CHROMEDRIVER_PATH")
        service = Service(
            chromedriver_path
            if chromedriver_path and os.path.exists(chromedriver_path)
            else ChromeDriverManager().install()
        )
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def extract_data_from_console(self):
        logs = self.driver.get_log("browser")
        if not logs:
            time.sleep(5)
            logs = self.driver.get_log("browser")
        for log_entry in reversed(logs):
            message = log_entry.get("message", "")
            if "updateMessageArea:" in message:
                match = re.search(
                    r"updateMessageArea:\s*(\d+)\s*,\s*(\d{1,2}:\d{2})\s*,\s*([\d,]+\.?\d*)\s*,\s*(\d*\.?\d+)",
                    message,
                )
                if match:
                    current_value_mw = float(match.group(3).replace(",", "").strip())
                    temperature_c = float(match.group(4).strip())
                    return {
                        "scrape_timestamp_utc": datetime.datetime.utcnow().isoformat(),
                        "display_date_id": match.group(1).strip(),
                        "display_time": match.group(2).strip(),
                        "current_value_MW": current_value_mw,
                        "temperature_C": temperature_c,
                    }
        date_id = self.driver.execute_script(
            "return document.querySelector('.messageHeader')?.innerText.trim().split(' ')[0];"
        )
        time_str = self.driver.execute_script(
            "return document.querySelector('.messageHeader')?.innerText.trim().split(' ')[1];"
        )
        power = self.driver.execute_script(
            "return document.querySelector('.messageValue')?.innerText.trim().replace(',','');"
        )
        temp = self.driver.execute_script(
            "return document.querySelector('.messageTemp')?.innerText.trim();"
        )
        if date_id and time_str and power and temp:
            return {
                "scrape_timestamp_utc": datetime.datetime.utcnow().isoformat(),
                "display_date_id": date_id,
                "display_time": time_str,
                "current_value_MW": float(power),
                "temperature_C": float(temp),
            }
        return None

    def scrape_once(self):
        self.driver.get(self.url)
        time.sleep(15)
        data = self.extract_data_from_console()
        if not data:
            time.sleep(10)
            data = self.extract_data_from_console()
        return data

    def close(self):
        self.driver.quit()


@task(cache_key_fn=None)
def initialize_scraper_task(url="https://www.sothailand.com/sysgen/egat/"):
    return EGATRealTimeScraper(url=url)


@task(cache_key_fn=None)
def scrape_data_task(scraper):
    return scraper.scrape_once()


@task
def process_and_store_data_task(
    new_data_dict: dict, lakefs_s3_path: str, storage_options: dict
):
    if not new_data_dict:
        return False
    existing_df = pd.DataFrame()
    try:
        existing_df = pd.read_parquet(lakefs_s3_path, storage_options=storage_options)
        existing_df["scrape_timestamp_utc"] = pd.to_datetime(
            existing_df["scrape_timestamp_utc"], errors="coerce"
        ).dt.tz_localize(None)
    except:
        pass
    new_df = pd.DataFrame([new_data_dict])
    new_df["scrape_timestamp_utc"] = pd.to_datetime(
        new_df["scrape_timestamp_utc"], errors="coerce"
    ).dt.tz_localize(None)
    combined_df = (
        pd.concat([existing_df, new_df], ignore_index=True)
        if not existing_df.empty
        else new_df
    )
    combined_df.sort_values(
        "scrape_timestamp_utc", ascending=True, inplace=True, na_position="last"
    )
    combined_df.drop_duplicates(
        subset=["display_date_id", "display_time"], keep="first", inplace=True
    )
    combined_df["scrape_timestamp_utc"] = combined_df["scrape_timestamp_utc"].astype(
        str
    )
    try:
        combined_df.to_parquet(
            lakefs_s3_path,
            storage_options=storage_options,
            index=False,
            engine="pyarrow",
            compression="snappy",
        )
        return True
    except:
        return False


@task
def commit_to_lakefs_task(
    repo_name: str,
    branch_name: str,
    access_key: str,
    secret_key: str,
    endpoint_url: str,
):
    try:
        client = lakefs.client.Client(
            endpoint=endpoint_url, access_key=access_key, secret_key=secret_key
        )
        commit_message = (
            f"Automatic commit of EGAT data at {datetime.datetime.utcnow().isoformat()}"
        )
        response = client.commit(
            repository=repo_name,
            branch=branch_name,
            message=commit_message,
            metadata={
                "source": "prefect_pipeline",
                "timestamp": datetime.datetime.utcnow().isoformat(),
            },
        )
        return True
    except:
        return False


@task(cache_key_fn=None)
def close_scraper_task(scraper):
    scraper.close()


@flow(name="EGAT Real-Time Power Data Pipeline")
def egat_data_pipeline():
    ACCESS_KEY = os.getenv("LAKEFS_ACCESS_KEY_ID", "access_key")
    SECRET_KEY = os.getenv("LAKEFS_SECRET_ACCESS_KEY", "secret_key")
    LAKEFS_ENDPOINT = os.getenv("LAKEFS_ENDPOINT_URL", "http://localhost:8001/")
    REPO_NAME = "dataset"
    BRANCH_NAME = "main"
    TARGET_PARQUET_FILE_PATH = "egat_datascraping/egat_realtime_power_history.parquet"
    lakefs_s3_path = f"s3a://{REPO_NAME}/{BRANCH_NAME}/{TARGET_PARQUET_FILE_PATH}"
    storage_options = {
        "key": ACCESS_KEY,
        "secret": SECRET_KEY,
        "client_kwargs": {"endpoint_url": LAKEFS_ENDPOINT},
    }
    scraper = initialize_scraper_task()
    max_retries = 3
    new_data = None
    for attempt in range(1, max_retries + 1):
        new_data = scrape_data_task(scraper)
        if new_data:
            break
        if attempt < max_retries:
            time.sleep(30)
    if new_data:
        storage_success = process_and_store_data_task(
            new_data, lakefs_s3_path, storage_options
        )
        if storage_success:
            commit_to_lakefs_task(
                repo_name=REPO_NAME,
                branch_name=BRANCH_NAME,
                access_key=ACCESS_KEY,
                secret_key=SECRET_KEY,
                endpoint_url=LAKEFS_ENDPOINT,
            )
    close_scraper_task(scraper)


if __name__ == "__main__":
    egat_data_pipeline()
