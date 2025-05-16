import time
import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import os
import re

class EGATRealTimeScraper:
    def __init__(self, url="https://www.sothailand.com/sysgen/egat/", output_file="egat_realtime_power.csv"):
        self.url = url
        self.output_file = output_file
        self.driver = None
        
    def _initialize_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def extract_data_from_console(self):
        logs = self.driver.get_log('browser')
        for log_entry in reversed(logs):
            message = log_entry.get('message', '')
            if 'updateMessageArea:' in message:
                match = re.search(r'updateMessageArea:\s*([\d\.]+)\s*,\s*([\d:]+)\s*,\s*([\d,]+\.\d+)\s*,\s*([\d\.-]+)', message)
                if match:
                    return {
                        'scrape_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'display_date_id': match.group(1).strip(),
                        'display_time': match.group(2).strip(),
                        'current_value_MW': float(match.group(3).replace(',', '')),
                        'temperature_C': float(match.group(4))
                    }
        return None

    def extract_data_from_html(self):
        wait = WebDriverWait(self.driver, 15)
        current_value = float(wait.until(EC.visibility_of_element_located((By.ID, "lbl_sysgen_value"))).text.replace(',', ''))
        datetime_text = wait.until(EC.visibility_of_element_located((By.ID, "lbl_datetime_value"))).text
        display_time = re.search(r'เวลา\s*(\d{1,2}:\d{2})\s*น.', datetime_text).group(1)
        temperature = float(re.search(r'([\d\.]+)', wait.until(EC.visibility_of_element_located((By.ID, "lbl_temp_value"))).text).group(1))
        
        return {
            'scrape_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'display_date_id': str(int(time.time())),
            'display_time': display_time,
            'current_value_MW': current_value,
            'temperature_C': temperature
        }

    def save_to_csv(self, data):
        if not data:
            return None
        df_new = pd.DataFrame([data])
        file_exists = os.path.exists(self.output_file) and os.path.getsize(self.output_file) > 0
        df_new.to_csv(self.output_file, mode='a' if file_exists else 'w', header=not file_exists, index=False)
        return df_new

    def scrape_once(self):
        self._initialize_driver()
        self.driver.get(self.url)
        time.sleep(10)
        
        data = self.extract_data_from_console() or self.extract_data_from_html()
        if data:
            self.save_to_csv(data)
            
        self.driver.quit()
        return data

if __name__ == "__main__":
    scraper = EGATRealTimeScraper()
    scraped_data = scraper.scrape_once()
    if scraped_data:
        print(pd.DataFrame([scraped_data]))