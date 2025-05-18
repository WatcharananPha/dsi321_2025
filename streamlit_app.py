import time
import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import re

class EGATRealTimeScraper:
    def __init__(self, url="https://www.sothailand.com/sysgen/egat/"):
        self.url = url
        self.driver = None

    def _initialize_driver(self):
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def extract_data_from_console(self) -> pd.DataFrame | None:
        if not self.driver:
            return None
        logs = self.driver.get_log('browser')
        for log_entry in reversed(logs):
            message = log_entry.get('message', '')
            match = re.search(r'updateMessageArea:\s*(\d+)\s*,\s*(\d{1,2}:\d{2})\s*,\s*([\d,]+\.\d+)\s*,\s*(\d+\.\d+)', message)
            if match:
                return pd.DataFrame([{
                    'scrape_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'display_date_id': match.group(1).strip(),
                    'display_time': match.group(2).strip(),
                    'current_value_MW': float(match.group(3).replace(',', '').strip()),
                    'temperature_C': float(match.group(4).strip())
                }])
        return None

    def scrape_once(self) -> pd.DataFrame | None:
        self._initialize_driver()
        self.driver.get(self.url)
        time.sleep(10)
        return self.extract_data_from_console()

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
