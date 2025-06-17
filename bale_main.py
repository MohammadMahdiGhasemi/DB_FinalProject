import httpx
import asyncio
import os
import json
import logging
from typing import List, Dict, Any, Optional
import psycopg2
import re

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# ثابت‌های مربوط به حالت‌های مکالمه
STATE_NONE = 0
STATE_REVIEW_EMAIL = 1
STATE_REVIEW_PHONE = 2
STATE_REVIEW_MOBILE = 3
STATE_REVIEW_RATING = 4
STATE_REVIEW_COMMENT = 5
STATE_ORDER_EMAIL = 6
STATE_ORDER_PHONE = 7
STATE_ORDER_MOBILE = 8
STATE_ORDER_QUANTITY = 9
STATE_ORDER_CONFIRM = 10
STATE_ORDER_LIST_EMAIL = 11
STATE_ORDER_LIST_PHONE = 12

# تنظیمات دیتابیس
DB_CONFIG = {
    'dbname': '402463101',
    'user': '402463101',
    'password': '402463101',
    'host': '78.38.35.219',
    'port': '5432'
}

# تنظیمات API بله
BALE_TOKEN = os.getenv('BALE_TOKEN', '188437706:onE6GV73BxJsoHYOO6aY2N9rOY7YoF8F3rdD3NYk')
BALE_API_URL = f"https://tapi.bale.ai/bot{BALE_TOKEN}"

# ذخیره داده‌های کاربران
user_data_store = {}

async def send_message(chat_id: int, text: str, reply_markup: Optional[Dict] = None):
    """ارسال پیام به کاربر با استفاده از API بله"""
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "chat_id": chat_id,
                "text": text
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            response = await client.post(f"{BALE_API_URL}/sendMessage", json=payload)
            response.raise_for_status()
            logger.debug(f"Message sent to {chat_id}: {text}")
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None

async def get_updates(offset: Optional[int] = None):
    """دریافت آپدیت‌های جدید از API بله"""
    async with httpx.AsyncClient() as client:
        try:
            params = {"offset": offset} if offset else {}
            response = await client.get(f"{BALE_API_URL}/getUpdates", params=params)
            response.raise_for_status()
            return response.json().get("result", [])
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []

async def delete_webhook():
    """حذف Webhook"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BALE_API_URL}/deleteWebhook")
            response.raise_for_status()
            logger.info("Webhook deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting webhook: {e}")

def test_token():
    """تست اعتبار توکن"""
    try:
        response = httpx.get(f"{BALE_API_URL}/getMe", timeout=10)
        data = response.json()
        logger.debug(f"Token test response: {data}")
        if data.get('ok'):
            logger.info(f"Token valid, bot username: {data['result']['username']}")
            return True
        else:
            logger.error(f"Invalid token response: {data}")
            return False
    except Exception as e:
        logger.error(f"Token test failed: {e}")
        return False

# توابع دیتابیس (بدون تغییر)
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.debug("Database connection established")
        return conn
    except Exception as e:
        logger.error(f"خطا در اتصال به دیتابیس: {e}")
        return None

def execute_query(query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("No database connection")
            return []
        cur = conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
        if cur.description:
            columns = [desc[0] for desc in cur.description]
            results = [dict(zip(columns, row)) for row in cur.fetchall()]
        else:
            results = []
        conn.commit()
        cur.close()
        conn.close()
        logger.debug(f"Query executed successfully: {query[:50]}...")
        return results
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

# توابع دیتابیس دیگر (مانند get_all_mobiles، search_by_brand و غیره) بدون تغییر باقی می‌مانند
def get_all_mobiles() -> List[Dict[str, Any]]:
    query = """
    SELECT 
        m.id,
        m.name AS mobile_name,
        b.name AS brand_name,
        m.price,
        m.release_date,
        s.ram,
        s.storage,
        s.processor,
        s.screen_size,
        s.battery_capacity,
        s.camera,
        COALESCE(AVG(r.rating), 0) AS average_rating,
        COUNT(DISTINCT r.id) AS review_count,
        STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
    FROM mobiles m
    LEFT JOIN brands b ON m.brand_id = b.id
    LEFT JOIN specifications s ON m.id = s.mobile_id
    LEFT JOIN reviews r ON m.id = r.mobile_id
    LEFT JOIN images i ON m.id = i.mobile_id
    GROUP BY m.id, m.name, b.name, m.price, m.release_date, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
    ORDER BY average_rating DESC, review_count DESC
    """
    return execute_query(query)

def search_by_brand(brand_name: str) -> List[Dict[str, Any]]:
    query = """
    SELECT 
        m.id,
        m.name AS mobile_name,
        b.name AS brand_name,
        m.price,
        s.ram,
        s.storage,
        s.processor,
        s.screen_size,
        s.battery_capacity,
        s.camera,
        COALESCE(AVG(r.rating), 0) AS average_rating,
        COUNT(DISTINCT r.id) AS review_count,
        STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
    FROM mobiles m
    JOIN brands b ON m.brand_id = b.id
    LEFT JOIN specifications s ON m.id = s.mobile_id
    LEFT JOIN reviews r ON m.id = r.mobile_id
    LEFT JOIN images i ON m.id = i.mobile_id
    WHERE b.name = %(brand_name)s
    GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
    ORDER BY average_rating DESC, review_count DESC
    """
    return execute_query(query, {'brand_name': brand_name})

def search_by_price_range(min_price: float, max_price: float) -> List[Dict[str, Any]]:
    query = """
    SELECT 
        m.id,
        m.name AS mobile_name,
        b.name AS brand_name,
        m.price,
        s.ram,
        s.storage,
        s.processor,
        s.screen_size,
        s.battery_capacity,
        s.camera,
        COALESCE(AVG(r.rating), 0) AS average_rating,
        COUNT(DISTINCT r.id) AS review_count,
        STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
    FROM mobiles m
    JOIN brands b ON m.brand_id = b.id
    LEFT JOIN specifications s ON m.id = s.mobile_id
    LEFT JOIN reviews r ON m.id = r.mobile_id
    LEFT JOIN images i ON m.id = i.mobile_id
    WHERE m.price BETWEEN %(min_price)s AND %(max_price)s
    GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
    ORDER BY m.price ASC
    """
    return execute_query(query, {'min_price': min_price, 'max_price': max_price})

def create_order(customer_info: Dict[str, str], order_items: List[Dict[str, Any]]) -> Optional[int]:
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("No database connection for order creation")
            return None
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO customers (name, email, phone)
            VALUES (%(name)s, %(email)s, %(phone)s)
            ON CONFLICT (email) DO UPDATE 
            SET name = EXCLUDED.name, phone = EXCLUDED.phone
            RETURNING id
        """, customer_info)
        customer_id = cur.fetchone()[0]
        total_price = sum(item['price'] * item['quantity'] for item in order_items)
        cur.execute("""
            INSERT INTO orders (customer_id, total_price)
            VALUES (%(customer_id)s, %(total_price)s)
            RETURNING id
        """, {'customer_id': customer_id, 'total_price': total_price})
        order_id = cur.fetchone()[0]
        for item in order_items:
            cur.execute("""
                INSERT INTO order_items (order_id, mobile_id, quantity, price)
                VALUES (%(order_id)s, %(mobile_id)s, %(quantity)s, %(price)s)
            """, {
                'order_id': order_id,
                'mobile_id': item['mobile_id'],
                'quantity': item['quantity'],
                'price': item['price']
            })
            cur.execute("""
                UPDATE stock
                SET quantity = quantity - %(quantity)s
                WHERE mobile_id = %(mobile_id)s
            """, {
                'mobile_id': item['mobile_id'],
                'quantity': item['quantity']
            })
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Order created successfully: {order_id}")
        return order_id
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return None

def get_reviews() -> List[Dict[str, Any]]:
    query = """
    SELECT 
        r.id AS review_id,
        c.name AS customer_name,
        m.name AS mobile_name,
        b.name AS brand_name,
        r.rating,
        r.comment,
        r.review_date,
        COUNT(DISTINCT r2.id) AS helpful_votes,
        STRING_AGG(DISTINCT i.image_url, ', ') AS mobile_images
    FROM reviews r
    JOIN customers c ON r.customer_id = c.id
    JOIN mobiles m ON r.mobile_id = m.id
    JOIN brands b ON m.brand_id = b.id
    LEFT JOIN reviews r2 ON r2.comment LIKE '%helpful%' AND r2.mobile_id = r.mobile_id
    LEFT JOIN images i ON m.id = i.mobile_id
    GROUP BY r.id, c.name, m.name, b.name, r.rating, r.comment, r.review_date
    ORDER BY r.review_date DESC, helpful_votes DESC
    """
    return execute_query(query)

def get_inventory() -> List[Dict[str, Any]]:
    query = """
    SELECT 
        s.id AS seller_id,
        se.name AS seller_name,
        m.name AS mobile_name,
        b.name AS brand_name,
        s.quantity,
        m.price,
        COUNT(DISTINCT oi.id) AS total_sold,
        COALESCE(AVG(r.rating), 0) AS average_rating,
        STRING_AGG(DISTINCT i.image_url, ', ') AS mobile_images
    FROM stock s
    JOIN sellers se ON s.seller_id = se.id
    JOIN mobiles m ON s.mobile_id = m.id
    JOIN brands b ON m.brand_id = b.id
    LEFT JOIN order_items oi ON m.id = oi.mobile_id
    LEFT JOIN reviews r ON m.id = r.mobile_id
    LEFT JOIN images i ON m.id = i.mobile_id
    GROUP BY s.id, se.name, m.name, b.name, s.quantity, m.price
    ORDER BY s.quantity DESC, total_sold DESC
    """
    return execute_query(query)

def get_special_offers() -> List[Dict[str, Any]]:
    query = """
    WITH popular_mobiles AS (
        SELECT 
            m.id,
            m.name,
            b.name AS brand_name,
            m.price,
            COUNT(DISTINCT oi.id) AS purchase_count,
            COALESCE(AVG(r.rating), 0) AS average_rating,
            COUNT(DISTINCT r.id) AS review_count
        FROM mobiles m
        JOIN brands b ON m.brand_id = b.id
        LEFT JOIN order_items oi ON m.id = oi.mobile_id
        LEFT JOIN reviews r ON m.id = r.mobile_id
        GROUP BY m.id, m.name, b.name, m.price
        HAVING COUNT(DISTINCT oi.id) > 10 OR COALESCE(AVG(r.rating), 0) >= 4
    )
    SELECT 
        pm.*,
        s.ram,
        s.storage,
        s.processor,
        s.screen_size,
        s.battery_capacity,
        s.camera,
        STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
    FROM popular_mobiles pm
    LEFT JOIN specifications s ON pm.id = s.mobile_id
    LEFT JOIN images i ON pm.id = i.mobile_id
    GROUP BY pm.id, pm.name, pm.brand_name, pm.price, pm.purchase_count, pm.average_rating, pm.review_count,
             s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
    ORDER BY purchase_count DESC, average_rating DESC
    """
    return execute_query(query)

def add_review(customer_id: int, mobile_id: int, rating: int, comment: str) -> Optional[int]:
    query = """
    INSERT INTO reviews (customer_id, mobile_id, rating, comment, review_date)
    VALUES (%(customer_id)s, %(mobile_id)s, %(rating)s, %(comment)s, CURRENT_TIMESTAMP)
    RETURNING id
    """
    results = execute_query(query, {
        'customer_id': customer_id,
        'mobile_id': mobile_id,
        'rating': rating,
        'comment': comment
    })
    if results:
        logger.info(f"Review added successfully: {results[0]['id']}")
        return results[0]['id']
    logger.error("Failed to add review")
    return None

def get_user_data(user_id: int) -> dict:
    """ذخیره و بازیابی داده‌های کاربر"""
    if user_id not in user_data_store:
        user_data_store[user_id] = {'state': STATE_NONE}
    return user_data_store[user_id]

async def create_reply_keyboard(buttons: List[List[str]]) -> Dict:
    """ایجاد JSON برای کیبورد پاسخ"""
    return {
        "keyboard": [[{"text": button} for button in row] for row in buttons],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

async def handle_start(chat_id: int):
    """مدیریت دستور /start"""
    try:
        keyboard = await create_reply_keyboard([
            ["📱 نمایش موبایل‌ها", "🔍 جستجوی پیشرفته"],
            ["🛒 سفارشات", "⭐ نظرات کاربران"],
            ["📋 موجودی مغازه‌ها", "🔥 پیشنهاد ویژه"],
            ["✍️ نظر بده", "ℹ️ راهنما"]
        ])
        welcome_text = """
🌟 به ربات فروشگاه موبایل خوش آمدید! 🌟

لطفاً یکی از گزینه‌های منو را انتخاب کنید:
"""
        await send_message(chat_id, welcome_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"خطا در تابع start: {e}")
        await send_message(chat_id, "متأسفانه خطایی رخ داده است.")

async def handle_message(chat_id: int, text: str, user_id: int):
    """مدیریت پیام‌های دریافتی"""
    try:
        logger.debug(f"Message received: {text} from user: {user_id}")
        user_data = get_user_data(user_id)
        state = user_data.get('state', STATE_NONE)
        logger.debug(f"User state: {state}")

        # نادیده گرفتن دستورات غیر از /start
        if text.startswith('/') and text != '/start':
            logger.debug(f"Ignoring command: {text}")
            return

        # مدیریت دستور /start
        if text == '/start':
            await handle_start(chat_id)
            return

        # مدیریت حالت‌های مکالمه
        if state == STATE_REVIEW_EMAIL:
            if '@' not in text or '.' not in text:
                await send_message(chat_id, "لطفاً یک ایمیل معتبر وارد کنید:")
                return
            user_data['email'] = text
            user_data['state'] = STATE_REVIEW_PHONE
            await send_message(chat_id, "لطفاً شماره موبایل خود را وارد کنید:")
            return

        elif state == STATE_REVIEW_PHONE:
            if not text.isdigit() or len(text) < 10:
                await send_message(chat_id, "لطفاً یک شماره موبایل معتبر وارد کنید:")
                return
            user_data['phone'] = text
            user_data['state'] = STATE_REVIEW_MOBILE
            query = """
            SELECT id, name, brand_name 
            FROM (
                SELECT m.id, m.name, b.name as brand_name
                FROM mobiles m
                JOIN brands b ON m.brand_id = b.id
            ) as mobile_list
            ORDER BY brand_name, name
            """
            mobiles = execute_query(query)
            if not mobiles:
                await send_message(chat_id, "متأسفانه هیچ موبایلی برای ثبت نظر موجود نیست.")
                user_data['state'] = STATE_NONE
                return
            keyboard = await create_reply_keyboard([[f"📱 {mobile['brand_name']} - {mobile['name']}"] for mobile in mobiles] + [["❌ انصراف"]])
            await send_message(chat_id, "لطفاً موبایل مورد نظر را انتخاب کنید:", reply_markup=keyboard)
            return

        elif state == STATE_REVIEW_MOBILE:
            if text == "❌ انصراف":
                user_data['state'] = STATE_NONE
                keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                await send_message(chat_id, "ثبت نظر لغو شد.", reply_markup=keyboard)
                return
            query = """
            SELECT m.id 
            FROM mobiles m
            JOIN brands b ON m.brand_id = b.id
            WHERE CONCAT(b.name, ' - ', m.name) = %(mobile_name)s
            """
            mobile_name = text.replace("📱 ", "")
            mobile = execute_query(query, {'mobile_name': mobile_name})
            if not mobile:
                await send_message(chat_id, "لطفاً یک برند و مدل معتبر انتخاب کنید:")
                return
            user_data['mobile_id'] = mobile[0]['id']
            user_data['state'] = STATE_REVIEW_RATING
            keyboard = await create_reply_keyboard([
                ["⭐", "⭐⭐", "⭐⭐⭐"],
                ["⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
                ["❌ انصراف"]
            ])
            await send_message(chat_id, "لطفاً امتیاز خود را انتخاب کنید:", reply_markup=keyboard)
            return

        elif state == STATE_REVIEW_RATING:
            if text == "❌ انصراف":
                user_data['state'] = STATE_NONE
                keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                await send_message(chat_id, "ثبت نظر لغو شد.", reply_markup=keyboard)
                return
            rating = len(text)
            if rating < 1 or rating > 5:
                await send_message(chat_id, "لطفاً یک امتیاز معتبر انتخاب کنید:")
                return
            user_data['rating'] = rating
            user_data['state'] = STATE_REVIEW_COMMENT
            keyboard = await create_reply_keyboard([["❌ انصراف"]])
            await send_message(chat_id, "لطفاً نظر خود را بنویسید:", reply_markup=keyboard)
            return

        elif state == STATE_REVIEW_COMMENT:
            if text == "❌ انصراف":
                user_data['state'] = STATE_NONE
                keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                await send_message(chat_id, "ثبت نظر لغو شد.", reply_markup=keyboard)
                return
            try:
                customer_query = """
                SELECT id FROM customers WHERE email = %(email)s
                """
                customer = execute_query(customer_query, {'email': user_data['email']})
                if not customer:
                    create_customer_query = """
                    INSERT INTO customers (email, name, phone) 
                    VALUES (%(email)s, %(email)s, %(phone)s)
                    RETURNING id
                    """
                    customer = execute_query(create_customer_query, {'email': user_data['email'], 'phone': user_data['phone']})
                customer_id = customer[0]['id']
                review_id = add_review(customer_id, user_data['mobile_id'], user_data['rating'], text)
                if review_id:
                    keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                    await send_message(chat_id, "✅ نظر شما با موفقیت ثبت شد.", reply_markup=keyboard)
                else:
                    keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                    await send_message(chat_id, "❌ خطا در ثبت نظر. لطفاً دوباره بررسی کنید.", reply_markup=keyboard)
                user_data['state'] = STATE_NONE
            except Exception as e:
                logger.error(f"Error adding review: {e}")
                keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                await send_message(chat_id, "❌ خطا در ثبت نظر. لطفاً دوباره بررسی کنید.", reply_markup=keyboard)
                user_data['state'] = STATE_NONE
            return

        elif state == STATE_ORDER_EMAIL:
            if '@' not in text or '.' not in text:
                await send_message(chat_id, "لطفاً یک ایمیل معتبر وارد کنید:")
                return
            user_data['email'] = text
            user_data['state'] = STATE_ORDER_PHONE
            await send_message(chat_id, "لطفاً شماره موبایل خود را وارد کنید:")
            return

        elif state == STATE_ORDER_PHONE:
            if not text.isdigit() or len(text) < 10:
                await send_message(chat_id, "لطفاً یک شماره موبایل معتبر وارد کنید:")
                return
            user_data['phone'] = text
            user_data['state'] = STATE_ORDER_MOBILE
            query = """
            SELECT 
                m.id,
                m.name,
                b.name AS brand_name,
                m.price,
                s.quantity
            FROM mobiles m
            JOIN brands b ON m.brand_id = b.id
            JOIN stock s ON m.id = s.mobile_id
            WHERE s.quantity > 0
            ORDER BY b.name, m.name
            """
            mobiles = execute_query(query)
            if not mobiles:
                keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                await send_message(chat_id, "متأسفانه هیچ موبایلی موجود نیست.", reply_markup=keyboard)
                user_data['state'] = STATE_NONE
                return
            keyboard = await create_reply_keyboard([[f"📱 {mobile['brand_name']} - {mobile['name']} ({mobile['price']:,.0f} تومان)"] for mobile in mobiles] + [["❌ انصراف"]])
            await send_message(chat_id, "لطفاً موبایل مورد نظر را انتخاب کنید:", reply_markup=keyboard)
            return

        elif state == STATE_ORDER_MOBILE:
            if text == "❌ انصراف":
                user_data['state'] = STATE_NONE
                keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                await send_message(chat_id, "سفارش لغو شد.", reply_markup=keyboard)
                return
            query = """
            SELECT m.id, m.price, s.quantity
            FROM mobiles m
            JOIN brands b ON m.brand_id = b.id
            JOIN stock s ON m.id = s.mobile_id
            WHERE CONCAT(b.name, ' - ', m.name) = %(mobile_name)s
            """
            mobile_name = text.split(" (")[0].replace("📱 ", "")
            mobile = execute_query(query, {'mobile_name': mobile_name})
            if not mobile:
                await send_message(chat_id, "لطفاً یک موبایل معتبر انتخاب کنید:")
                return
            user_data['mobile_id'] = mobile[0]['id']
            user_data['mobile_price'] = mobile[0]['price']
            user_data['available_quantity'] = mobile[0]['quantity']
            user_data['state'] = STATE_ORDER_QUANTITY
            keyboard = await create_reply_keyboard([[str(i)] for i in range(1, min(6, mobile[0]['quantity'] + 1))] + [["❌ انصراف"]])
            await send_message(chat_id, f"لطفاً تعداد مورد نظر را انتخاب کنید (حداکثر {mobile[0]['quantity']}):", reply_markup=keyboard)
            return

        elif state == STATE_ORDER_QUANTITY:
            if text == "❌ انصراف":
                user_data['state'] = STATE_NONE
                keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                await send_message(chat_id, "سفارش لغو شد.", reply_markup=keyboard)
                return
            try:
                quantity = int(text)
                if quantity < 1 or quantity > user_data['available_quantity']:
                    await send_message(chat_id, f"لطفاً یک عدد بین 1 تا {user_data['available_quantity']} وارد کنید:")
                    return
                user_data['quantity'] = quantity
                total_price = quantity * user_data['mobile_price']
                query = """
                SELECT m.name, b.name as brand_name
                FROM mobiles m
                JOIN brands b ON m.brand_id = b.id
                WHERE m.id = %(mobile_id)s
                """
                mobile = execute_query(query, {'mobile_id': user_data['mobile_id']})
                confirmation_text = f"""
📋 خلاصه سفارش:

📱 موبایل: {mobile[0]['brand_name']} - {mobile[0]['name']}
📦 تعداد: {quantity}
💰 قیمت واحد: {user_data['mobile_price']:,.0f} تومان
💰 قیمت کل: {total_price:,.0f} تومان

آیا مایل به ثبت سفارش هستید؟
"""
                keyboard = await create_reply_keyboard([["✅ تأیید سفارش"], ["❌ انصراف"]])
                await send_message(chat_id, confirmation_text, reply_markup=keyboard)
                user_data['state'] = STATE_ORDER_CONFIRM
            except ValueError:
                await send_message(chat_id, "لطفاً یک عدد معتبر وارد کنید:")
            return

        elif state == STATE_ORDER_CONFIRM:
            if text == "❌ انصراف":
                user_data['state'] = STATE_NONE
                keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                await send_message(chat_id, "سفارش لغو شد.", reply_markup=keyboard)
                return
            if text != "✅ تأیید سفارش":
                await send_message(chat_id, "لطفاً تأیید یا انصراف را انتخاب کنید:")
                return
            try:
                order_items = [{
                    'mobile_id': user_data['mobile_id'],
                    'quantity': user_data['quantity'],
                    'price': user_data['mobile_price']
                }]
                customer_info = {
                    'email': user_data['email'],
                    'phone': user_data['phone'],
                    'name': user_data['email']
                }
                order_id = create_order(customer_info, order_items)
                keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                if order_id:
                    await send_message(chat_id, f"✅ سفارش شما با موفقیت ثبت شد.\nشماره سفارش: {order_id}", reply_markup=keyboard)
                else:
                    await send_message(chat_id, "❌ خطا در ثبت سفارش. لطفاً دوباره بررسی کنید.", reply_markup=keyboard)
                user_data['state'] = STATE_NONE
            except Exception as e:
                logger.error(f"Error creating order: {e}")
                keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
                await send_message(chat_id, "❌ خطا در ثبت سفارش. لطفاً دوباره بررسی کنید.", reply_markup=keyboard)
                user_data['state'] = STATE_NONE
            return

        elif state == STATE_ORDER_LIST_EMAIL:
            if text == "🔙 بازگشت":
                user_data['state'] = STATE_NONE
                keyboard = await create_reply_keyboard([["🛒 سفارش جدید", "📋 لیست سفارشات"], ["🔙 بازگشت"]])
                await send_message(chat_id, "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=keyboard)
                return
            if '@' not in text or '.' not in text:
                await send_message(chat_id, "لطفاً یک ایمیل معتبر وارد کنید:")
                return
            query = """
            SELECT 
                o.id AS order_id,
                o.order_date,
                o.total_price,
                STRING_AGG(CONCAT(m.name, ' (', oi.quantity, ')'), ', ') AS items
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN order_items oi ON o.id = oi.order_id
            JOIN mobiles m ON oi.mobile_id = m.id
            WHERE c.email = %(email)s
            GROUP BY o.id, o.order_date, o.total_price
            ORDER BY o.order_date DESC
            """
            orders = execute_query(query, {'email': text})
            if orders:
                response = "📋 لیست سفارشات شما:\n\n"
                for order in orders:
                    response += f"""
🛒 سفارش #{order['order_id']}
📅 تاریخ: {order['order_date']}
📦 اقلام: {order['items']}
💰 مبلغ کل: {order['total_price']:,.0f} تومان
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, "هیچ سفارشی با این ایمیل یافت نشد.")
            user_data['state'] = STATE_NONE
            keyboard = await create_reply_keyboard([["🛒 سفارش جدید", "📋 لیست سفارشات"], ["🔙 بازگشت"]])
            await send_message(chat_id, "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=keyboard)
            return

        elif state == STATE_ORDER_LIST_PHONE:
            if text == "🔙 بازگشت":
                user_data['state'] = STATE_NONE
                keyboard = await create_reply_keyboard([["🛒 سفارش جدید", "📋 لیست سفارشات"], ["🔙 بازگشت"]])
                await send_message(chat_id, "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=keyboard)
                return
            if not text.isdigit() or len(text) < 10:
                await send_message(chat_id, "لطفاً یک شماره تماس معتبر وارد کنید:")
                return
            query = """
            SELECT 
                o.id AS order_id,
                o.order_date,
                o.total_price,
                STRING_AGG(CONCAT(m.name, ' (', oi.quantity, ')'), ', ') AS items
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN order_items oi ON o.id = oi.order_id
            JOIN mobiles m ON oi.mobile_id = m.id
            WHERE c.phone = %(phone)s
            GROUP BY o.id, o.order_date, o.total_price
            ORDER BY o.order_date DESC
            """
            orders = execute_query(query, {'phone': text})
            if orders:
                response = "📋 لیست سفارشات شما:\n\n"
                for order in orders:
                    response += f"""
🛒 سفارش #{order['order_id']}
📅 تاریخ: {order['order_date']}
📦 اقلام: {order['items']}
💰 مبلغ کل: {order['total_price']:,.0f} تومان
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, "هیچ سفارشی با این شماره تماس یافت نشد.")
            user_data['state'] = STATE_NONE
            keyboard = await create_reply_keyboard([["🛒 سفارش جدید", "📋 لیست سفارشات"], ["🔙 بازگشت"]])
            await send_message(chat_id, "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=keyboard)
            return

        # مدیریت گزینه‌های منو
        if text == "📱 نمایش موبایل‌ها":
            mobiles = get_all_mobiles()
            if mobiles:
                response = "📱 لیست موبایل‌ها:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, "متأسفانه هیچ موبایلی یافت نشد.")

        elif text == "🔍 جستجوی پیشرفته":
            keyboard = await create_reply_keyboard([
                ["📱 بر اساس برند", "💰 بر اساس قیمت"],
                ["⚙️ بر اساس مشخصات", "🔙 بازگشت"]
            ])
            await send_message(chat_id, "روش جستجو را انتخاب کنید:", reply_markup=keyboard)

        elif text == "📱 بر اساس برند":
            query = "SELECT DISTINCT name FROM brands ORDER BY name"
            brands = execute_query(query)
            if brands:
                keyboard = []
                for i in range(0, len(brands), 2):
                    row = [f"📱 {brands[i]['name']}"]
                    if i + 1 < len(brands):
                        row.append(f"📱 {brands[i+1]['name']}")
                    keyboard.append(row)
                keyboard.append(["🔙 بازگشت"])
                reply_markup = await create_reply_keyboard(keyboard)
                await send_message(chat_id, "برند مورد نظر را انتخاب کنید:", reply_markup=reply_markup)
            else:
                await send_message(chat_id, "متأسفانه هیچ برندی یافت نشد.")

        elif text.startswith("📱 ") and text not in ["📱 بر اساس برند", "📱 نمایش موبایل‌ها", "📱 RAM"]:
            brand_name = text.replace("📱 ", "")
            mobiles = search_by_brand(brand_name)
            if mobiles:
                response = f"📱 موبایل‌های برند {brand_name}:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, f"متأسفانه هیچ موبایلی از برند {brand_name} یافت نشد.")

        elif text == "💰 بر اساس قیمت":
            keyboard = await create_reply_keyboard([
                ["💰 تا 5 میلیون", "💰 5 تا 10 میلیون"],
                ["💰 10 تا 15 میلیون", "💰 15 تا 20 میلیون"],
                ["💰 بالای 20 میلیون", "🔙 بازگشت"]
            ])
            await send_message(chat_id, "محدوده قیمت را انتخاب کنید:", reply_markup=keyboard)

        elif text in ["💰 تا 5 میلیون", "💰 5 تا 10 میلیون", "💰 10 تا 15 میلیون", "💰 15 تا 20 میلیون", "💰 بالای 20 میلیون"]:
            price_ranges = {
                "💰 تا 5 میلیون": (0, 5000000),
                "💰 5 تا 10 میلیون": (5000000, 10000000),
                "💰 10 تا 15 میلیون": (10000000, 15000000),
                "💰 15 تا 20 میلیون": (15000000, 20000000),
                "💰 بالای 20 میلیون": (20000000, float('inf'))
            }
            min_price, max_price = price_ranges[text]
            mobiles = search_by_price_range(min_price, max_price)
            if mobiles:
                response = f"📱 موبایل‌های {text}:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, f"متأسفانه هیچ موبایلی در این محدوده قیمت یافت نشد.")

        elif text == "⭐ نظرات کاربران":
            reviews = get_reviews()
            if reviews:
                response = "⭐ نظرات کاربران:\n\n"
                for review in reviews:
                    response += f"""
📱 {review['mobile_name']}
🏷️ برند: {review['brand_name']}
👤 کاربر: {review['customer_name']}
⭐ امتیاز: {review['rating']}/5
💬 نظر: {review['comment']}
📅 تاریخ: {review['review_date']}
👍 مفید: {review['helpful_votes']}
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, "هنوز هیچ نظری ثبت نشده است.")

        elif text == "📋 موجودی مغازه‌ها":
            inventory = get_inventory()
            if inventory:
                response = "📋 موجودی مغازه‌ها:\n\n"
                for item in inventory:
                    response += f"""
🏪 فروشنده: {item['seller_name']}
📱 {item['mobile_name']}
🏷️ برند: {item['brand_name']}
📦 موجودی: {item['quantity']}
💰 قیمت: {item['price']:,.0f} تومان
📊 فروش: {item['total_sold']}
⭐ امتیاز: {item['average_rating']:.1f}
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, "متأسفانه اطلاعات موجودی در دسترس نیست.")

        elif text == "🔥 پیشنهاد ویژه":
            offers = get_special_offers()
            if offers:
                response = "🔥 پیشنهادهای ویژه:\n\n"
                for offer in offers:
                    response += f"""
📱 {offer['name']}
🏷️ برند: {offer['brand_name']}
💰 قیمت: {offer['price']:,.0f} تومان
📊 فروش: {offer['purchase_count']}
⭐ امتیاز: {offer['average_rating']:.1f} ({offer['review_count']} نظر)
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, "در حال حاضر پیشنهاد ویژه‌ای موجود نیست.")

        elif text == "✍️ نظر بده":
            user_data['state'] = STATE_REVIEW_EMAIL
            await send_message(chat_id, "لطفاً ایمیل خود را وارد کنید:")
            return

        elif text == "🛒 سفارشات":
            keyboard = await create_reply_keyboard([
                ["🛒 سفارش جدید", "📋 لیست سفارشات"],
                ["🔙 بازگشت"]
            ])
            await send_message(chat_id, "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=keyboard)

        elif text == "🛒 سفارش جدید":
            user_data['state'] = STATE_ORDER_EMAIL
            await send_message(chat_id, "لطفاً ایمیل خود را وارد کنید:")
            return

        elif text == "📋 لیست سفارشات":
            user_data['state'] = STATE_ORDER_LIST_EMAIL
            keyboard = await create_reply_keyboard([
                ["📧 جستجو با ایمیل", "📱 جستجو با شماره تماس"],
                ["🔙 بازگشت"]
            ])
            await send_message(chat_id, "لطفاً روش جستجوی سفارشات را انتخاب کنید:", reply_markup=keyboard)
            return

        elif text == "📧 جستجو با ایمیل":
            user_data['state'] = STATE_ORDER_LIST_EMAIL
            keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
            await send_message(chat_id, "لطفاً ایمیل خود را وارد کنید:", reply_markup=keyboard)
            return

        elif text == "📱 جستجو با شماره تماس":
            user_data['state'] = STATE_ORDER_LIST_PHONE
            keyboard = await create_reply_keyboard([["🔙 بازگشت"]])
            await send_message(chat_id, "لطفاً شماره تماس خود را وارد کنید:", reply_markup=keyboard)
            return

        elif text == "ℹ️ راهنما":
            await send_message(chat_id, """
📚 راهنمای استفاده از ربات:

1️⃣ نمایش موبایل‌ها: لیست کامل با جزئیات
2️⃣ جستجوی پیشرفته: بر اساس برند، قیمت یا مشخصات
3️⃣ سفارش جدید: ورود اطلاعات و تأیید
4️⃣ نظرات کاربران: مشاهده و ثبت نظر
5️⃣ موجودی مغازه‌ها: چک کردن موجودی
6️⃣ پیشنهاد ویژه: پرفروش‌ها و تخفیف‌ها
""")

        elif text == "🔙 بازگشت":
            await handle_start(chat_id)

        elif text == "⚙️ بر اساس مشخصات":
            keyboard = await create_reply_keyboard([
                ["📱 RAM", "💾 حافظه"],
                ["🔋 باتری", "📷 دوربین"],
                ["💻 پردازنده", "📺 صفحه نمایش"],
                ["🔙 بازگشت"]
            ])
            await send_message(chat_id, "مشخصه مورد نظر را انتخاب کنید:", reply_markup=keyboard)

        elif text == "📱 RAM":
            keyboard = await create_reply_keyboard([
                ["4GB", "6GB"],
                ["8GB", "12GB"],
                ["16GB", "🔙 بازگشت"]
            ])
            await send_message(chat_id, "مقدار RAM مورد نظر را انتخاب کنید:", reply_markup=keyboard)

        elif text in ["4GB", "6GB", "8GB", "12GB", "16GB"]:
            query = """
            SELECT 
                m.id,
                m.name AS mobile_name,
                b.name AS brand_name,
                m.price,
                s.ram,
                s.storage,
                s.processor,
                s.screen_size,
                s.battery_capacity,
                s.camera,
                COALESCE(AVG(r.rating), 0) AS average_rating,
                COUNT(DISTINCT r.id) AS review_count,
                STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
            FROM mobiles m
            JOIN brands b ON m.brand_id = b.id
            LEFT JOIN specifications s ON m.id = s.mobile_id
            LEFT JOIN reviews r ON m.id = r.mobile_id
            LEFT JOIN images i ON m.id = i.mobile_id
            WHERE s.ram = %(ram)s
            GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
            ORDER BY m.price ASC
            """
            mobiles = execute_query(query, {'ram': text})
            if mobiles:
                response = f"📱 موبایل‌های با {text} RAM:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
⚡ RAM: {mobile['ram']}
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, f"متأسفانه هیچ موبایلی با {text} RAM یافت نشد.")

        elif text == "💾 حافظه":
            keyboard = await create_reply_keyboard([
                ["64GB", "128GB"],
                ["256GB", "512GB"],
                ["1TB", "🔙 بازگشت"]
            ])
            await send_message(chat_id, "مقدار حافظه مورد نظر را انتخاب کنید:", reply_markup=keyboard)

        elif text in ["64GB", "128GB", "256GB", "512GB", "1TB"]:
            query = """
            SELECT 
                m.id,
                m.name AS mobile_name,
                b.name AS brand_name,
                m.price,
                s.ram,
                s.storage,
                s.processor,
                s.screen_size,
                s.battery_capacity,
                s.camera,
                COALESCE(AVG(r.rating), 0) AS average_rating,
                COUNT(DISTINCT r.id) AS review_count,
                STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
            FROM mobiles m
            JOIN brands b ON m.brand_id = b.id
            LEFT JOIN specifications s ON m.id = s.mobile_id
            LEFT JOIN reviews r ON m.id = r.mobile_id
            LEFT JOIN images i ON m.id = i.mobile_id
            WHERE s.storage = %(storage)s
            GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
            ORDER BY m.price ASC
            """
            mobiles = execute_query(query, {'storage': text})
            if mobiles:
                response = f"📱 موبایل‌های با حافظه {text}:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
💾 حافظه: {mobile['storage']}
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, f"متأسفانه هیچ موبایلی با حافظه {text} یافت نشد.")

        elif text == "🔋 باتری":
            keyboard = await create_reply_keyboard([
                ["3000-4000 mAh", "4000-5000 mAh"],
                ["5000-6000 mAh", "6000+ mAh"],
                ["🔙 بازگشت"]
            ])
            await send_message(chat_id, "ظرفیت باتری مورد نظر را انتخاب کنید:", reply_markup=keyboard)

        elif text in ["3000-4000 mAh", "4000-5000 mAh", "5000-6000 mAh", "6000+ mAh"]:
            capacity_ranges = {
                "3000-4000 mAh": (3000, 4000),
                "4000-5000 mAh": (4000, 5000),
                "5000-6000 mAh": (5000, 6000),
                "6000+ mAh": (6000, 10000)
            }
            min_capacity, max_capacity = capacity_ranges[text]
            query = """
            SELECT 
                m.id,
                m.name AS mobile_name,
                b.name AS brand_name,
                m.price,
                s.ram,
                s.storage,
                s.processor,
                s.screen_size,
                s.battery_capacity,
                s.camera,
                COALESCE(AVG(r.rating), 0) AS average_rating,
                COUNT(DISTINCT r.id) AS review_count,
                STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
            FROM mobiles m
            JOIN brands b ON m.brand_id = b.id
            LEFT JOIN specifications s ON m.id = s.mobile_id
            LEFT JOIN reviews r ON m.id = r.mobile_id
            LEFT JOIN images i ON m.id = i.mobile_id
            WHERE CAST(REGEXP_REPLACE(s.battery_capacity, '[^0-9]', '') AS INTEGER) BETWEEN %(min_capacity)s AND %(max_capacity)s
            GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
            ORDER BY m.price ASC
            """
            mobiles = execute_query(query, {'min_capacity': min_capacity, 'max_capacity': max_capacity})
            if mobiles:
                response = f"📱 موبایل‌های با باتری {text}:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
🔋 باتری: {mobile['battery_capacity']}
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, f"متأسفانه هیچ موبایلی با باتری {text} یافت نشد.")

        elif text == "📷 دوربین":
            keyboard = await create_reply_keyboard([
                ["12MP", "48MP"],
                ["50MP", "64MP"],
                ["108MP", "🔙 بازگشت"]
            ])
            await send_message(chat_id, "رزولوشن دوربین اصلی مورد نظر را انتخاب کنید:", reply_markup=keyboard)

        elif text in ["12MP", "48MP", "50MP", "64MP", "108MP"]:
            query = """
            SELECT 
                m.id,
                m.name AS mobile_name,
                b.name AS brand_name,
                m.price,
                s.ram,
                s.storage,
                s.processor,
                s.screen_size,
                s.battery_capacity,
                s.camera,
                COALESCE(AVG(r.rating), 0) AS average_rating,
                COUNT(DISTINCT r.id) AS review_count,
                STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
            FROM mobiles m
            JOIN brands b ON m.brand_id = b.id
            LEFT JOIN specifications s ON m.id = s.mobile_id
            LEFT JOIN reviews r ON m.id = r.mobile_id
            LEFT JOIN images i ON m.id = i.mobile_id
            WHERE s.camera LIKE %(camera)s
            GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
            ORDER BY m.price ASC
            """
            mobiles = execute_query(query, {'camera': f'%{text}%'})
            if mobiles:
                response = f"📱 موبایل‌های با دوربین {text}:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
📷 دوربین: {mobile['camera']}
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, f"متأسفانه هیچ موبایلی با دوربین {text} یافت نشد.")

        elif text == "💻 پردازنده":
            keyboard = await create_reply_keyboard([
                ["Snapdragon", "MediaTek"],
                ["Exynos", "Apple A"],
                ["سایر", "🔙 بازگشت"]
            ])
            await send_message(chat_id, "نوع پردازنده مورد نظر را انتخاب کنید:", reply_markup=keyboard)

        elif text in ["Snapdragon", "MediaTek", "Exynos", "Apple A", "سایر"]:
            if text == "Apple A":
                query = """
                SELECT 
                    m.id,
                    m.name AS mobile_name,
                    b.name AS brand_name,
                    m.price,
                    s.ram,
                    s.storage,
                    s.processor,
                    s.screen_size,
                    s.battery_capacity,
                    s.camera,
                    COALESCE(AVG(r.rating), 0) AS average_rating,
                    COUNT(DISTINCT r.id) AS review_count,
                    STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
                FROM mobiles m
                JOIN brands b ON m.brand_id = b.id
                LEFT JOIN specifications s ON m.id = s.mobile_id
                LEFT JOIN reviews r ON m.id = r.mobile_id
                LEFT JOIN images i ON m.id = i.mobile_id
                WHERE s.processor ~ '^A[0-9]{1,2}(.*)?'
                GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
                ORDER BY m.price ASC
                """
                mobiles = execute_query(query)
            elif text == "سایر":
                query = """
                SELECT 
                    m.id,
                    m.name AS mobile_name,
                    b.name AS brand_name,
                    m.price,
                    s.ram,
                    s.storage,
                    s.processor,
                    s.screen_size,
                    s.battery_capacity,
                    s.camera,
                    COALESCE(AVG(r.rating), 0) AS average_rating,
                    COUNT(DISTINCT r.id) AS review_count,
                    STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
                FROM mobiles m
                JOIN brands b ON m.brand_id = b.id
                LEFT JOIN specifications s ON m.id = s.mobile_id
                LEFT JOIN reviews r ON m.id = r.mobile_id
                LEFT JOIN images i ON m.id = i.mobile_id
                WHERE 
                    s.processor IS NOT NULL 
                    AND s.processor NOT LIKE '%Snapdragon%'
                    AND s.processor NOT LIKE '%MediaTek%'
                    AND s.processor NOT LIKE '%Exynos%'
                    AND s.processor !~ '^A[0-9]{1,2}(.*)?'
                GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
                ORDER BY m.price ASC
                """
                mobiles = execute_query(query)
            else:
                query = """
                SELECT 
                    m.id,
                    m.name AS mobile_name,
                    b.name AS brand_name,
                    m.price,
                    s.ram,
                    s.storage,
                    s.processor,
                    s.screen_size,
                    s.battery_capacity,
                    s.camera,
                    COALESCE(AVG(r.rating), 0) AS average_rating,
                    COUNT(DISTINCT r.id) AS review_count,
                    STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
                FROM mobiles m
                JOIN brands b ON m.brand_id = b.id
                LEFT JOIN specifications s ON m.id = s.mobile_id
                LEFT JOIN reviews r ON m.id = r.mobile_id
                LEFT JOIN images i ON m.id = i.mobile_id
                WHERE LOWER(s.processor) LIKE LOWER(%(processor)s)
                GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
                ORDER BY m.price ASC
                """
                mobiles = execute_query(query, {'processor': f'%{text}%'})
            if mobiles:
                response = f"📱 موبایل‌های با پردازنده {text}:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
⚙️ پردازنده: {mobile['processor']}
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, f"متأسفانه هیچ موبایلی با پردازنده {text} یافت نشد.")

        elif text == "📺 صفحه نمایش":
            keyboard = await create_reply_keyboard([
                ["5-6 اینچ", "6-6.5 اینچ"],
                ["6.5-7 اینچ", "7+ اینچ"],
                ["🔙 بازگشت"]
            ])
            await send_message(chat_id, "اندازه صفحه نمایش مورد نظر را انتخاب کنید:", reply_markup=keyboard)

        elif text in ["5-6 اینچ", "6-6.5 اینچ", "6.5-7 اینچ", "7+ اینچ"]:
            size_ranges = {
                "5-6 اینچ": (5, 6),
                "6-6.5 اینچ": (6, 6.5),
                "6.5-7 اینچ": (6.5, 7),
                "7+ اینچ": (7, 10)
            }
            min_size, max_size = size_ranges[text]
            query = """
            SELECT 
                m.id,
                m.name AS mobile_name,
                b.name AS brand_name,
                m.price,
                s.ram,
                s.storage,
                s.processor,
                s.screen_size,
                s.battery_capacity,
                s.camera,
                COALESCE(AVG(r.rating), 0) AS average_rating,
                COUNT(DISTINCT r.id) AS review_count,
                STRING_AGG(DISTINCT i.image_url, ', ') AS image_urls
            FROM mobiles m
            JOIN brands b ON m.brand_id = b.id
            LEFT JOIN specifications s ON m.id = s.mobile_id
            LEFT JOIN reviews r ON m.id = r.mobile_id
            LEFT JOIN images i ON m.id = i.mobile_id
            WHERE 
                CASE 
                    WHEN s.screen_size ~ '^[0-9.]+' THEN 
                        CAST(REGEXP_REPLACE(s.screen_size, '[^0-9.]', '') AS FLOAT) BETWEEN %(min_size)s AND %(max_size)s
                    WHEN s.screen_size ~ '^[0-9.]+\\s*inch' THEN 
                        CAST(REGEXP_REPLACE(s.screen_size, '[^0-9.]', '') AS FLOAT) BETWEEN %(min_size)s AND %(max_size)s
                    WHEN s.screen_size ~ '^[0-9.]+\\s*اینچ' THEN 
                        CAST(REGEXP_REPLACE(s.screen_size, '[^0-9.]', '') AS FLOAT) BETWEEN %(min_size)s AND %(max_size)s
                    ELSE FALSE
                END
            GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
            ORDER BY m.price ASC
            """
            mobiles = execute_query(query, {'min_size': min_size, 'max_size': max_size})
            if mobiles:
                response = f"📱 موبایل‌های با صفحه نمایش {text}:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
📺 صفحه نمایش: {mobile['screen_size']}
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await send_message(chat_id, response)
            else:
                await send_message(chat_id, f"متأسفانه هیچ موبایلی با صفحه نمایش {text} یافت نشد.")

        else:
            await send_message(chat_id, "گزینه نامعتبر! لطفاً از منو استفاده کنید.")

    except Exception as e:
        logger.error(f"خطا در تابع handle_message: {e}")
        await send_message(chat_id, "متأسفانه خطایی رخ داده است.")

async def polling():
    """حلقه Polling برای دریافت آپدیت‌ها"""
    offset = None
    while True:
        try:
            updates = await get_updates(offset)
            for update in updates:
                offset = update.get("update_id") + 1
                message = update.get("message")
                if not message:
                    continue
                chat_id = message.get("chat", {}).get("id")
                user_id = message.get("from", {}).get("id")
                text = message.get("text")
                if not (chat_id and user_id and text):
                    continue
                await handle_message(chat_id, text, user_id)
            await asyncio.sleep(1)  # جلوگیری از درخواست‌های بیش از حد
        except Exception as e:
            logger.error(f"Error in polling: {e}")
            await asyncio.sleep(5)  # در صورت خطا، کمی صبر کنید

def main():
    try:
        logger.info("Starting bot...")
        logger.debug(f"Bot token: {BALE_TOKEN[:10]}...")
        if not test_token():
            logger.error("Bot cannot start due to invalid token")
            exit(1)
        asyncio.run(delete_webhook())
        asyncio.run(polling())
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        exit(1)

if __name__ == '__main__':
    main()