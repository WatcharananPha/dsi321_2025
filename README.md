# EGAT Real-time Power Generation Scraper

## Overview 

This Python script fetches real-time electricity production data from the Electricity Generating Authority of Thailand (EGAT) website at the URL `https://www.sothailand.com/sysgen/egat/` using Selenium to interact with the web page and pulls data from the browser's Console Log, where the website dynamically updates data. The script is designed to run continuously, capturing new data at specified intervals.

## Benefits

- **Real-time Monitoring**: Captures live electricity production data directly from EGAT's systems, enabling immediate visibility into Thailand's power grid status.

- **Automated Data Collection**: Eliminates manual data gathering by automatically scraping data at configurable intervals, ensuring consistent historical datasets.

- **Predictive Analytics**: Powers forecasting models to predict electricity demand patterns, enabling better resource planning and optimization.

- **Interactive Visualization**: Presents complex power generation data through an intuitive user interface, making insights accessible to both technical and non-technical users.

- **Technical Innovation**: Leverages Selenium for dynamic content extraction from console logs, demonstrating an advanced web scraping approach for JavaScript-heavy websites.

- **Historical Analysis**: Builds a comprehensive time-series dataset suitable for trend analysis and anomaly detection in power generation.

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

- **Tools Used**
    - **Web Scraping**: Python `webdriver_manager` `Selenium`
    - **Data Validation**: `Pydantic`
    - **Data Storage**: `lakeFS`
    - **Orchestration**: `Prefect`
    - **Visualization**: `Streamlit`
    - **CI/CD**: GitHub Actions

- **Hardware Requirements**
    - Docker-compatible environment
    - Local or cloud system with:
        - At least 4 GB RAM
        - Internet access for EGAT web
        - Port availability for Prefect UI (default: `localhost:4200`)

## Prepare

- **Setup Steps**
    - Create a virtual environment
    ```bash
    python -m venv .venv
    ```
    - Install required packages
    ```bash
    #Windows config
    pip install -r test_scraping\requirements.txt
    ```
    ```bash
    #mac-os
    pip install -r test_scraping\requirements.txt
    ```
    - Activate the virtual environment
    ```bash
    #Windows config
    source .venv/Scripts/activate
    ```
    ```bash
    #mac-os
    source .venv/bin/activate
    ```

## Running Prefect

- Create a deployment for build, push, and pull for building Docker images, pushing code to the Docker registry, and pulling code to run the flow.
- **If there is a PREFECT_API_URL bug, run this script first.**
    ```bash
    #Windows config
    $env:PREFECT_API_URL = "http://127.0.0.1:4200/api"
    ```
    ```bash
    #mac-os
    export PREFECT_API_URL="http://127.0.0.1:4200/api"
    ```
- Deployments allow you to run flows on a schedule and trigger runs based on events.
    ```bash
    prefect deploy
    ```
- Start Prefect Worker to start pulling jobs from the Work Pool and Work Queue.
    ```bash
    pefect worker start --pool 'default-agent-pool' --work-queue 'default'
    ```
- Run Streamlit UI
    ```bash
    streamlit run UI/streamlit_app.py
    ```