from prefect import flow, task
from scraper_egat import EGATRealTimeScraper

CSV_OUTPUT_FILE = "egat_realtime_power.csv"

@task(retries=2, retry_delay_seconds=60)
def scrape_egat_data_task():
    scraper = EGATRealTimeScraper(output_file=CSV_OUTPUT_FILE)
    return scraper.scrape_once()

@flow
def egat_realtime_pipeline():
    scrape_egat_data_task.submit()

if __name__ == "__main__":
    egat_realtime_pipeline()