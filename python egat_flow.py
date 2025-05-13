import time
import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
import re
from prefect import flow, task
from prefect.logging import get_run_logger

class EGATRealTimeScraper:
    def __init__(self, url="https://www.sothailand.com/sysgen/egat/", output_file="egat_power_data.csv"):
        self.logger = get_run_logger()
        self.url = url
        self.output_file = output_file
        self.driver = None
        
    def _initialize_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--log-level=0")
        chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def extract_data_from_console(self):
        if not self.driver:
            return None

        logs = self.driver.get_log('browser')
        for log_entry in logs:
            message = log_entry.get('message', '')
            if 'updateMessageArea:' in message:
                match = re.search(r'updateMessageArea:\s+(\d+)\s*,\s*(\d+:\d+)\s*,\s*([\d,]+\.\d+)\s*,\s*(\d+\.\d+)', message)
                if match:
                    display_date_id = match.group(1).strip()
                    display_time = match.group(2).strip()
                    current_value_mw = float(match.group(3).replace(',', '').strip())
                    temperature_c = float(match.group(4).strip())
                    return {
                        'scrape_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'display_date_id': display_date_id,
                        'display_time': display_time,
                        'current_value_MW': current_value_mw,
                        'temperature_C': temperature_c
                    }
        return None

    def save_to_csv(self, new_data):
        if not new_data:
            return None

        df_new = pd.DataFrame([new_data])
        output_dir = os.path.dirname(self.output_file)

        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if os.path.exists(self.output_file):
            df_new.to_csv(self.output_file, mode='a', header=False, index=False, encoding='utf-8')
        else:
            df_new.to_csv(self.output_file, index=False, encoding='utf-8')
        return self.output_file

    def scrape_once(self):
        if self.driver is None:
            self._initialize_driver()

        self.driver.get(self.url)
        time.sleep(5)
        data = self.extract_data_from_console()
        saved_file = None
        if data:
            saved_file = self.save_to_csv(data)
        return data, saved_file

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

@task
def run_single_scrape(scraper: EGATRealTimeScraper) -> tuple:
    return scraper.scrape_once()

@task
def close_scraper_driver(scraper: EGATRealTimeScraper):
    scraper.close()

@flow(name="EGAT Realtime Scrape - Single Run")
def egat_scrape_single_run_flow(
    url: str = "https://www.sothailand.com/sysgen/egat/",
    output_file: str = "data/egat_realtime_power.csv"
):
    logger = get_run_logger()
    scraper = None
    
    scraper = EGATRealTimeScraper(url=url, output_file=output_file)
    scraped_data, saved_to = run_single_scrape(scraper)
    
    if scraper:
        close_scraper_driver(scraper)

if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")
    egat_scrape_single_run_flow(output_file="data/egat_test_run.csv")   