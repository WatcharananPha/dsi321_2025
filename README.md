# EGAT Real-time Power Generation Scraper

## Overview 

This Python script fetches real-time electricity production data from the Electricity Generating Authority of Thailand (EGAT) website at the URL `https://www.sothailand.com/sysgen/egat/` using Selenium to interact with the web page and pulls data from the browser's Console Log, where the website dynamically updates data. The script is designed to run continuously, capturing new data at specified intervals.

## Dataset Quality

| Quality Check | Description | Status |
|--------------|-------------|--------|
| Contains at least 1,000 records | Ensures dataset has sufficient volume | ✅ Passing |
| Covers a full 24-hour time range | Verifies complete daily coverage | ✅ Passing |
| At least 90% data completeness | Checks for minimal missing values | ✅ Passing |
| No columns with data type 'object' | Ensures proper data typing | ✅ Passing |
| No duplicate records | Confirms data uniqueness | ✅ Passing |

- Dataset (`parquet\egat_realtime_power_history.parquet`)


## Project structure

```
DSI321_2025/
├── _pycache_/
│   └── egat_pipeline.cpython-312.pyc
├── parquet/
│   └── egat_realtime_power_history.parquet
├── test-scraping/
│   ├── .ipynb_checkpoints/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── run_scraper_and_save_to_lakefs.ipynb
├── UI/
│   └── streamlit_app.py
├── docker-compose.yml
├── egat_pipeline.py
├── egat_realtime_power.csv
├── prefect.yaml
└── README.md
```

## Resources

## Prepare

## Running Prefect

