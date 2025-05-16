# EGAT Real-time Power Generation Scraper

สคริปต์ Python นี้ทำหน้าที่ดึงข้อมูลการผลิตไฟฟ้าแบบเรียลไทม์จากเว็บไซต์การไฟฟ้าฝ่ายผลิตแห่งประเทศไทย (กฟผ.) โดยใช้ Selenium ในการโต้ตอบกับหน้าเว็บ และดึงข้อมูลจาก Console Log ของเบราว์เซอร์

## โครงสร้างโปรเจค

```
.
├── config/                         # ไฟล์การตั้งค่าต่างๆ
│   ├── docker/                    # Docker configurations
│   ├── logging/                   # การตั้งค่า logging
│   └── path_config.py            # การกำหนดค่า path และ URL
├── data_output/                   # ข้อมูลที่ได้จากการ scrape
│   └── egat/
├── src/                          # โค้ดหลัก
│   ├── backend/                  # ส่วนประมวลผลหลัก
│   │   ├── scraping/            # โค้ดสำหรับ scraping
│   │   ├── pipeline/            # กระบวนการทำงาน
│   │   └── validation/          # การตรวจสอบข้อมูล
│   └── frontend/                # ส่วนแสดงผล
└── test/                        # Unit tests
```

## คุณสมบัติเด่น

*   **ดึงข้อมูลแบบเรียลไทม์:** ดึงข้อมูลตัวเลขการผลิตไฟฟ้าล่าสุดและอุณหภูมิ
*   **วิเคราะห์ Console Log:** ดึงข้อมูลจาก JavaScript Console Log โดยตรง
*   **ทำงานแบบ Headless:** ใช้ Selenium ในโหมด Headless
*   **Docker Support:** รองรับการทำงานผ่าน Docker
*   **Modular Design:** แยกส่วนการทำงานเป็นโมดูลชัดเจน
*   **Logging System:** ระบบ logging ที่ปรับแต่งได้
*   **Data Validation:** มีระบบตรวจสอบความถูกต้องของข้อมูล

## การติดตั้ง

1. **Clone Repository:**
```bash
git clone <repository_url>
cd <repository_directory>
```

2. **ติดตั้ง Dependencies:**
```bash
pip install -r requirements.txt
```

3. **ตั้งค่า Environment:**
```bash
cp .env.example .env
# แก้ไขค่าใน .env ตามต้องการ
```

## การใช้งาน

### แบบ Python Script
```bash
python src/backend/pipeline/run_egat_scraper.py
```

### แบบ Docker
```bash
docker-compose up -d
```

## การพัฒนา

1. **สร้าง Virtual Environment:**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. **ติดตั้ง Development Dependencies:**
```bash
pip install -r requirements-dev.txt
```

## การทดสอบ
```bash
python -m pytest
```

## Configuration

การตั้งค่าหลักอยู่ในไฟล์ต่างๆ ดังนี้:
- `.env` - ค่า environment variables
- `config/path_config.py` - การกำหนด path และ URL
- `config/logging/modern_log.py` - การตั้งค่า logging

## การจัดการข้อมูล

ข้อมูลที่ scrape ได้จะถูกเก็บที่:
```
data_output/egat/egat_realtime_power.csv
```

## License

[ระบุ License ที่ใช้]