# Database Project with Telegram and Bale Bots

This project implements a database system with bot interfaces for both Telegram and Bale messaging platforms.
این پروژه یک سیستم پایگاه داده با رابط‌های ربات برای پلتفرم‌های پیام‌رسانی تلگرام و بله پیاده‌سازی می‌کند.

## Project Structure | ساختار پروژه

- `main.py` - Main Telegram bot implementation | پیاده‌سازی ربات تلگرام
- `bale_main.py` - Bale bot implementation | پیاده‌سازی ربات بله
- `create_tables.sql` - SQL scripts for creating database tables | اسکریپت‌های SQL برای ایجاد جداول پایگاه داده
- `queries.sql` - SQL queries for database operations | کوئری‌های SQL برای عملیات پایگاه داده
- `requirment.txt` - Project dependencies | وابستگی‌های پروژه

## Requirements | نیازمندی‌ها

The project requires Python 3.x and the following main dependencies:

پروژه به Python 3.x و وابستگی‌های اصلی زیر نیاز دارد:

- Balethon - For Bale bot implementation | برای پیاده‌سازی ربات بله
- python-telegram-bot - For Telegram bot implementation | برای پیاده‌سازی ربات تلگرام
- psycopg2-binary - PostgreSQL database adapter | رابط پایگاه داده PostgreSQL
- aiohttp - Asynchronous HTTP client/server | کلاینت/سرور HTTP ناهمگام
- requests - HTTP library for Python | کتابخانه HTTP برای پایتون

## Setup | راه‌اندازی

1. Create a virtual environment | ایجاد محیط مجازی:
```bash
python -m venv .venv
```

2. Activate the virtual environment | فعال‌سازی محیط مجازی:
- Windows | ویندوز:
```bash
.venv\Scripts\activate
```
- Linux/Mac | لینوکس/مک:
```bash
source .venv/bin/activate
```

3. Install dependencies | نصب وابستگی‌ها:
```bash
pip install -r requirment.txt
```

4. Set up your database using the SQL scripts | راه‌اندازی پایگاه داده با استفاده از اسکریپت‌های SQL:
```bash
psql -U your_username -d your_database -f create_tables.sql
```

5. Configure your bot tokens in the respective files | تنظیم توکن‌های ربات در فایل‌های مربوطه

6. Run the bots | اجرای ربات‌ها:
- For Telegram bot | برای ربات تلگرام:
```bash
python main.py
```
- For Bale bot | برای ربات بله:
```bash
python bale_main.py
```

## Database Configuration | پیکربندی پایگاه داده

The project uses PostgreSQL as its database. You need to set up the following environment variables:
این پروژه از PostgreSQL به عنوان پایگاه داده استفاده می‌کند. شما باید متغیرهای محیطی زیر را تنظیم کنید:

```bash
DB_HOST=your_database_host
DB_PORT=your_database_port
DB_NAME=your_database_name
DB_USER=your_database_username
DB_PASSWORD=your_database_password
```

## Environment Variables | متغیرهای محیطی

For the bots to work properly, you need to set up the following environment variables:
برای عملکرد صحیح ربات‌ها، شما باید متغیرهای محیطی زیر را تنظیم کنید:

```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
BALE_BOT_TOKEN=your_bale_bot_token
```

---
