# EGAT Real-time Power Generation Scraper

สคริปต์ Python นี้ทำหน้าที่ดึงข้อมูลการผลิตไฟฟ้าแบบเรียลไทม์จากเว็บไซต์การไฟฟ้าฝ่ายผลิตแห่งประเทศไทย (กฟผ.) ที่ URL `https://www.sothailand.com/sysgen/egat/` โดยใช้ Selenium ในการโต้ตอบกับหน้าเว็บ และดึงข้อมูลจาก Console Log ของเบราว์เซอร์ ซึ่งเป็นที่ที่เว็บไซต์อัปเดตข้อมูลแบบไดนามิก ข้อมูลที่ดึงมาได้จะถูกบันทึกลงในไฟล์ CSV

สคริปต์ถูกออกแบบมาให้สามารถทำงานได้อย่างต่อเนื่อง เพื่อเก็บข้อมูลใหม่ตามช่วงเวลาที่กำหนด

## โครงสร้างโปรเจค

```
egat-scraper-project/
├── src/
│   ├── __init__.py
│   ├── scraper/
│   │   ├── __init__.py
│   │   └── egat_scraper.py        # Contains EGATRealTimeScraper class
│   ├── config.py                  # Configuration settings
│   ├── tasks.py                   # Prefect task definitions
│   └── flows.py                   # Prefect flow definitions
├── notebooks/
│   └── run_scraper_and_save_to_lakefs.ipynb  # Your original notebook for reference
├── run_scheduled_flow.py          # Script to run/deploy the Prefect flow
├── requirements.txt               # Project dependencies
├── docker-compose.yml             # Existing docker-compose
└── .env                           # For environment variables (you'll create this)
```

## คุณสมบัติเด่น

* **ดึงข้อมูลแบบเรียลไทม์:** ดึงข้อมูลตัวเลขการผลิตไฟฟ้าล่าสุดและอุณหภูมิ
* **วิเคราะห์ Console Log:** มีวิธีการเฉพาะในการดึงข้อมูลจากข้อความใน JavaScript Console Log ทำให้ไม่ต้องจัดการกับโครงสร้าง HTML ที่ซับซ้อน
* **ทำงานแบบ Headless:** ใช้ Selenium กับ Chrome ในโหมด Headless (ไม่มีหน้าจอ) เพื่อการทำงานเบื้องหลังอย่างมีประสิทธิภาพ
* **จัดการ ChromeDriver อัตโนมัติ:** ผสานการทำงานกับ `webdriver-manager` เพื่อดาวน์โหลดและจัดการเวอร์ชันของ ChromeDriver ให้ถูกต้องโดยอัตโนมัติ
* **บันทึกข้อมูลเป็น CSV:** ต่อท้ายข้อมูลใหม่ลงในไฟล์ CSV (สร้างไฟล์ใหม่หากยังไม่มี) พร้อมทั้งบันทึกเวลาที่ทำการดึงข้อมูล (timestamp)
* **ดึงข้อมูลต่อเนื่อง:** สามารถทำงานไปเรื่อยๆ เพื่อเก็บข้อมูลตามช่วงเวลาที่ผู้ใช้กำหนด
* **การบันทึก Log:** มีการบันทึก Log การทำงานพื้นฐานเพื่อติดตามการทำงานของสคริปต์และปัญหาที่อาจเกิดขึ้น

## หลักการทำงาน

เว็บไซต์ `https://www.sothailand.com/sysgen/egat/` ดูเหมือนจะอัปเดตข้อมูลที่แสดงผล (กำลังการผลิตปัจจุบันหน่วยเป็น MW และอุณหภูมิ) ผ่าน JavaScript ซึ่ง JavaScript นี้ก็จะส่งข้อความการอัปเดตไปยัง Console ของเบราว์เซอร์ด้วย สคริปต์นี้ใช้ประโยชน์จากพฤติกรรมดังกล่าว:

1. **เริ่มต้น WebDriver:** ตั้งค่าและเปิดเบราว์เซอร์ Chrome ในโหมด Headless ผ่าน Selenium และเปิดใช้งาน `goog:loggingPrefs` เพื่อเก็บ Log จาก Console ของเบราว์เซอร์
2. **เปิด URL เป้าหมาย:** เปิดหน้าเว็บ กฟผ. ที่ระบุ
3. **รอข้อมูล:** หยุดรอสักครู่เพื่อให้หน้าเว็บโหลดสมบูรณ์และ JavaScript ทำงาน
4. **ดึงข้อมูลจาก Console:** เรียกดู Log จาก Console ของเบราว์เซอร์ และค้นหาข้อความที่มีรูปแบบ `updateMessageArea:`
5. **แยกส่วนข้อมูล:** ใช้ Regular Expression เพื่อแยกส่วนข้อมูลที่เกี่ยวข้อง (เช่น รหัสวันที่, เวลา, ค่า MW ปัจจุบัน, อุณหภูมิ) ออกจากข้อความ Log ที่ตรงกัน
6. **บันทึกลง CSV:** จัดรูปแบบข้อมูลที่ดึงมาได้พร้อมกับ `scrape_time` (เวลาที่ดึงข้อมูล) ให้อยู่ในรูป Dictionary และบันทึกเป็นแถวใหม่ต่อท้ายไฟล์ CSV ที่กำหนด
7. **ทำงานวนซ้ำ (ทางเลือก):** หากมีการเรียกใช้ `scrape_continuously` สคริปต์จะทำซ้ำขั้นตอนที่ 2-6 ตามช่วงเวลาที่กำหนด
8. **ปิด WebDriver:** ปิดการทำงานของเบราว์เซอร์ Driver อย่างถูกต้องเมื่อสคริปต์ทำงานเสร็จหรือถูกขัดจังหวะ

## สิ่งที่ต้องมีก่อนเริ่มใช้งาน

* Python 3.7 ขึ้นไป
* ติดตั้งเบราว์เซอร์ Google Chrome

## การติดตั้งและตั้งค่า

1. **Clone Repository (ถ้ามี) หรือบันทึกไฟล์สคริปต์:**
```bash
# ถ้าเป็น Repository
# git clone <repository_url>
# cd <repository_directory>
```

2. **สร้าง Virtual Environment (แนะนำ):**
```bash
python -m venv venv
source venv/bin/activate  # สำหรับ Windows: venv\Scripts\activate
```

3. **ติดตั้ง Package ที่จำเป็น:**
```txt
pandas
selenium
webdriver-manager
```

จากนั้นรันคำสั่ง:
```bash
pip install -r requirements.txt
```