# EGAT Real-time Power Generation Scraper

## Overview 

สคริปต์ Python นี้ทำหน้าที่ดึงข้อมูลการผลิตไฟฟ้าแบบเรียลไทม์จากเว็บไซต์การไฟฟ้าฝ่ายผลิตแห่งประเทศไทย (กฟผ.) ที่ URL `https://www.sothailand.com/sysgen/egat/` โดยใช้ Selenium ในการโต้ตอบกับหน้าเว็บ และดึงข้อมูลจาก Console Log ของเบราว์เซอร์ ซึ่งเป็นที่ที่เว็บไซต์อัปเดตข้อมูลแบบไดนามิก    สคริปต์ถูกออกแบบมาให้สามารถทำงานได้อย่างต่อเนื่อง เพื่อเก็บข้อมูลใหม่ตามช่วงเวลาที่กำหนด

## Dataset Quality

| Quality Check | Description | Status |
|--------------|-------------|--------|
| Contains at least 1,000 records | Ensures dataset has sufficient volume | ✅ Passing |
| Covers a full 24-hour time range | Verifies complete daily coverage | ✅ Passing |
| At least 90% data completeness | Checks for minimal missing values | ✅ Passing |
| No columns with data type 'object' | Ensures proper data typing | ✅ Passing |
| No duplicate records | Confirms data uniqueness | ✅ Passing |

- Dataset ('parquet\egat_realtime_power_history.parquet')


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

