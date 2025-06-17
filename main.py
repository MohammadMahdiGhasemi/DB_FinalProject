import psycopg2
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
import logging
import sys
from typing import List, Dict, Any, Optional
import json

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تنظیمات دیتابیس
DB_CONFIG = {
    'dbname': '402463101',
    'user': '402463101',
    'password': '402463101',
    'host': '78.38.35.219',
    'port': '5432'
}

# اتصال به دیتابیس
def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"خطا در اتصال به دیتابیس: {e}")
        return None

# توابع دیتابیس
def execute_query(query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Execute a query and return results as a list of dictionaries"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cur = conn.cursor()
        if params:
            cur.execute(query, params)
        else:
            cur.execute(query)
            
        if cur.description:  # If the query returns results
            columns = [desc[0] for desc in cur.description]
            results = [dict(zip(columns, row)) for row in cur.fetchall()]
        else:
            results = []
            
        conn.commit()
        cur.close()
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []

def get_all_mobiles() -> List[Dict[str, Any]]:
    """Get all mobiles with their specifications and ratings"""
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
    """Search mobiles by brand"""
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
    """Search mobiles by price range"""
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
    """Create a new order with transaction"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cur = conn.cursor()
        
        # Insert customer
        cur.execute("""
            INSERT INTO customers (name, email, phone)
            VALUES (%(name)s, %(email)s, %(phone)s)
            ON CONFLICT (email) DO UPDATE 
            SET name = EXCLUDED.name, phone = EXCLUDED.phone
            RETURNING id
        """, customer_info)
        customer_id = cur.fetchone()[0]
        
        # Calculate total price
        total_price = sum(item['price'] * item['quantity'] for item in order_items)
        
        # Insert order
        cur.execute("""
            INSERT INTO orders (customer_id, total_price)
            VALUES (%(customer_id)s, %(total_price)s)
            RETURNING id
        """, {'customer_id': customer_id, 'total_price': total_price})
        order_id = cur.fetchone()[0]
        
        # Insert order items
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
            
            # Update stock
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
        return order_id
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return None

def get_reviews() -> List[Dict[str, Any]]:
    """Get all reviews with customer and mobile details"""
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
    """Get inventory with seller and mobile details"""
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
    """Get popular and highly rated mobiles"""
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

def add_review(email: str, mobile_id: int, rating: int, comment: str) -> Optional[int]:
    """Add a new review"""
    query = """
    INSERT INTO reviews (customer_id, mobile_id, rating, comment)
    VALUES (
        (SELECT id FROM customers WHERE email = %(email)s),
        %(mobile_id)s,
        %(rating)s,
        %(comment)s
    )
    RETURNING id
    """
    results = execute_query(query, {
        'email': email,
        'mobile_id': mobile_id,
        'rating': rating,
        'comment': comment
    })
    return results[0]['id'] if results else None

# Add these constants
REVIEW_EMAIL, REVIEW_PHONE, REVIEW_MOBILE, REVIEW_RATING, REVIEW_COMMENT = range(5)

# Add these constants after the existing REVIEW constants
ORDER_EMAIL, ORDER_PHONE, ORDER_MOBILE, ORDER_QUANTITY, ORDER_CONFIRM = range(5)

# Add these constants after the existing constants
ORDER_LIST_EMAIL, ORDER_LIST_PHONE = range(2)

# Add this function to store user data temporarily
def get_user_data(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> dict:
    if 'user_data' not in context.bot_data:
        context.bot_data['user_data'] = {}
    if user_id not in context.bot_data['user_data']:
        context.bot_data['user_data'][user_id] = {}
    return context.bot_data['user_data'][user_id]

# تابع شروع ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        keyboard = [
            ["📱 نمایش موبایل‌ها", "🔍 جستجوی پیشرفته"],
            ["🛒 سفارشات", "⭐ نظرات کاربران"],
            ["📋 موجودی مغازه‌ها", "🔥 پیشنهاد ویژه"],
            ["✍️ نظر بده", "ℹ️ راهنما"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        welcome_text = """
🌟 به ربات فروشگاه موبایل خوش آمدید! 🌟

لطفاً یکی از گزینه‌های زیر را انتخاب کنید:
"""
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"خطا در تابع start: {e}")
        await update.message.reply_text("متأسفانه خطایی رخ داده است.")

# تابع مدیریت پیام‌ها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        user_id = update.effective_chat.id

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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("متأسفانه هیچ موبایلی یافت نشد.")

        elif text == "🔍 جستجوی پیشرفته":
            keyboard = [
                ["📱 بر اساس برند", "💰 بر اساس قیمت"],
                ["⚙️ بر اساس مشخصات", "🔙 بازگشت"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("روش جستجو را انتخاب کنید:", reply_markup=reply_markup)

        elif text == "📱 بر اساس برند":
            # Get all brands from the database
            query = "SELECT DISTINCT name FROM brands ORDER BY name"
            brands = execute_query(query)
            if brands:
                keyboard = []
                # Calculate number of complete pairs
                num_pairs = len(brands) // 2
                # Handle complete pairs
                for i in range(num_pairs):
                    keyboard.append([
                        f"📱 {brands[i*2]['name']}", 
                        f"📱 {brands[i*2+1]['name']}"
                    ])
                # Handle remaining brand if odd number
                if len(brands) % 2 == 1:
                    keyboard.append([f"📱 {brands[-1]['name']}"])
                keyboard.append(["🔙 بازگشت"])
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
                await update.message.reply_text("برند مورد نظر را انتخاب کنید:", reply_markup=reply_markup)
            else:
                await update.message.reply_text("متأسفانه هیچ برندی یافت نشد.")

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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text(f"متأسفانه هیچ موبایلی با {text} RAM یافت نشد.")

        elif text.startswith("📱") and text != "📱 بر اساس برند" and text != "📱 نمایش موبایل‌ها" and text != "📱 RAM":
            # This is a brand selection
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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text(f"متأسفانه هیچ موبایلی از برند {brand_name} یافت نشد.")

        elif text == "💰 بر اساس قیمت":
            keyboard = [
                ["💰 تا 5 میلیون", "💰 5 تا 10 میلیون"],
                ["💰 10 تا 15 میلیون", "💰 15 تا 20 میلیون"],
                ["💰 بالای 20 میلیون", "🔙 بازگشت"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("محدوده قیمت را انتخاب کنید:", reply_markup=reply_markup)

        elif text == "💰 تا 5 میلیون":
            mobiles = search_by_price_range(0, 5000000)
            if mobiles:
                response = "📱 موبایل‌های زیر 5 میلیون:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("متأسفانه هیچ موبایلی در این محدوده قیمت یافت نشد.")

        elif text == "💰 5 تا 10 میلیون":
            mobiles = search_by_price_range(5000000, 10000000)
            if mobiles:
                response = "📱 موبایل‌های 5 تا 10 میلیون:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("متأسفانه هیچ موبایلی در این محدوده قیمت یافت نشد.")

        elif text == "💰 10 تا 15 میلیون":
            mobiles = search_by_price_range(10000000, 15000000)
            if mobiles:
                response = "📱 موبایل‌های 10 تا 15 میلیون:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("متأسفانه هیچ موبایلی در این محدوده قیمت یافت نشد.")

        elif text == "💰 15 تا 20 میلیون":
            mobiles = search_by_price_range(15000000, 20000000)
            if mobiles:
                response = "📱 موبایل‌های 15 تا 20 میلیون:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("متأسفانه هیچ موبایلی در این محدوده قیمت یافت نشد.")

        elif text == "💰 بالای 20 میلیون":
            mobiles = search_by_price_range(20000000, float('inf'))
            if mobiles:
                response = "📱 موبایل‌های بالای 20 میلیون:\n\n"
                for mobile in mobiles:
                    response += f"""
📱 {mobile['mobile_name']}
🏷️ برند: {mobile['brand_name']}
💰 قیمت: {mobile['price']:,.0f} تومان
⭐ امتیاز: {mobile['average_rating']:.1f} ({mobile['review_count']} نظر)
-------------------"""
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("متأسفانه هیچ موبایلی در این محدوده قیمت یافت نشد.")

        elif text == "⭐ نظرات کاربران":
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
            reviews = execute_query(query)
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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("هنوز هیچ نظری ثبت نشده است.")

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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("متأسفانه اطلاعات موجودی در دسترس نیست.")

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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("در حال حاضر پیشنهاد ویژه‌ای موجود نیست.")

        elif text == "✍️ نظر بده":
            await update.message.reply_text("""
لطفاً اطلاعات نظر خود را به این صورت وارد کنید:
ایمیل|شناسه موبایل|امتیاز (1-5)|نظر

مثال:
user@example.com|1|5|عالی بود!
""")

        elif text == "ℹ️ راهنما":
            await update.message.reply_text("""
📚 راهنمای استفاده از ربات:

1️⃣ نمایش موبایل‌ها: لیست کامل با جزئیات
2️⃣ جستجوی پیشرفته: بر اساس برند، قیمت یا مشخصات
3️⃣ سفارش جدید: ورود اطلاعات و تأیید
4️⃣ نظرات کاربران: مشاهده و ثبت نظر
5️⃣ موجودی مغازه‌ها: چک کردن موجودی
6️⃣ پیشنهاد ویژه: پرفروش‌ها و تخفیف‌ها
""")

        elif text == "🔙 بازگشت":
            await start(update, context)

        elif text == "⚙️ بر اساس مشخصات":
            keyboard = [
                ["📱 RAM", "💾 حافظه"],
                ["🔋 باتری", "📷 دوربین"],
                ["💻 پردازنده", "📺 صفحه نمایش"],
                ["🔙 بازگشت"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("مشخصه مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

        elif text == "📱 RAM":
            keyboard = [
                ["4GB", "6GB"],
                ["8GB", "12GB"],
                ["16GB", "🔙 بازگشت"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("مقدار RAM مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

        elif text == "💾 حافظه":
            keyboard = [
                ["64GB", "128GB"],
                ["256GB", "512GB"],
                ["1TB", "🔙 بازگشت"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("مقدار حافظه مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text(f"متأسفانه هیچ موبایلی با حافظه {text} یافت نشد.")

        elif text == "🔋 باتری":
            keyboard = [
                ["3000-4000 mAh", "4000-5000 mAh"],
                ["5000-6000 mAh", "6000+ mAh"],
                ["🔙 بازگشت"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("ظرفیت باتری مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

        elif text in ["3000-4000 mAh", "4000-5000 mAh", "5000-6000 mAh", "6000+ mAh"]:
            if text == "3000-4000 mAh":
                min_capacity = 3000
                max_capacity = 4000
            elif text == "4000-5000 mAh":
                min_capacity = 4000
                max_capacity = 5000
            elif text == "5000-6000 mAh":
                min_capacity = 5000
                max_capacity = 6000
            else:  # 6000+ mAh
                min_capacity = 6000
                max_capacity = 10000  # A reasonable upper limit

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
            WHERE CAST(REPLACE(REPLACE(s.battery_capacity, ' mAh', ''), 'mAh', '') AS INTEGER) BETWEEN %(min_capacity)s AND %(max_capacity)s
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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text(f"متأسفانه هیچ موبایلی با باتری {text} یافت نشد.")

        elif text == "📷 دوربین":
            keyboard = [
                ["12MP", "48MP"],
                ["50MP", "64MP"],
                ["108MP", "🔙 بازگشت"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("رزولوشن دوربین اصلی مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text(f"متأسفانه هیچ موبایلی با دوربین {text} یافت نشد.")

        elif "|" in text:
            try:
                email, mobile_id, rating, comment = text.split("|")
                # First check if the customer exists
                customer_query = """
                SELECT id FROM customers WHERE email = %(email)s
                """
                customer = execute_query(customer_query, {'email': email})
                
                if not customer:
                    # Create new customer
                    create_customer_query = """
                    INSERT INTO customers (email, name) 
                    VALUES (%(email)s, %(email)s)
                    RETURNING id
                    """
                    customer = execute_query(create_customer_query, {'email': email})
                
                customer_id = customer[0]['id']
                
                # Add the review
                review_query = """
                INSERT INTO reviews (customer_id, mobile_id, rating, comment, review_date)
                VALUES (%(customer_id)s, %(mobile_id)s, %(rating)s, %(comment)s, CURRENT_TIMESTAMP)
                RETURNING id
                """
                review = execute_query(review_query, {
                    'customer_id': customer_id,
                    'mobile_id': int(mobile_id),
                    'rating': int(rating),
                    'comment': comment
                })
                
                if review:
                    await update.message.reply_text("✅ نظر شما با موفقیت ثبت شد.")
                else:
                    await update.message.reply_text("❌ خطا در ثبت نظر. لطفاً اطلاعات را بررسی کنید.")
            except Exception as e:
                logger.error(f"Error adding review: {e}")
                await update.message.reply_text("❌ فرمت پیام اشتباه است. لطفاً از راهنما استفاده کنید.")

        elif text == "🛒 سفارشات":
            keyboard = [
                ["🛒 سفارش جدید", "📋 لیست سفارشات"],
                ["🔙 بازگشت"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)

        elif text == "📋 لیست سفارشات":
            # Get user's orders
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
            orders = execute_query(query, {'email': context.user_data.get('email', '')})
            
            if orders:
                response = "📋 لیست سفارشات شما:\n\n"
                for order in orders:
                    response += f"""
🛒 سفارش #{order['order_id']}
📅 تاریخ: {order['order_date']}
📦 اقلام: {order['items']}
💰 مبلغ کل: {order['total_price']:,.0f} تومان
-------------------"""
                await update.message.reply_text(response)
            else:
                await update.message.reply_text("شما هنوز سفارشی ثبت نکرده‌اید.")

        elif text == "💻 پردازنده":
            keyboard = [
                ["Snapdragon", "MediaTek"],
                ["Exynos", "Apple A"],
                ["سایر", "🔙 بازگشت"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("نوع پردازنده مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text(f"متأسفانه هیچ موبایلی با پردازنده {text} یافت نشد.")

        elif text in ["5-6 اینچ", "6-6.5 اینچ", "6.5-7 اینچ", "7+ اینچ"]:
            if text == "5-6 اینچ":
                min_size = 5
                max_size = 6
            elif text == "6-6.5 اینچ":
                min_size = 6
                max_size = 6.5
            elif text == "6.5-7 اینچ":
                min_size = 6.5
                max_size = 7
            else:  # 7+ اینچ
                min_size = 7
                max_size = 10  # A reasonable upper limit

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
                        CAST(REGEXP_REPLACE(s.screen_size, '[^0-9.]', '', 'g') AS FLOAT) BETWEEN %(min_size)s AND %(max_size)s
                    WHEN s.screen_size ~ '^[0-9.]+\\s*inch' THEN 
                        CAST(REGEXP_REPLACE(s.screen_size, '[^0-9.]', '', 'g') AS FLOAT) BETWEEN %(min_size)s AND %(max_size)s
                    WHEN s.screen_size ~ '^[0-9.]+\\s*اینچ' THEN 
                        CAST(REGEXP_REPLACE(s.screen_size, '[^0-9.]', '', 'g') AS FLOAT) BETWEEN %(min_size)s AND %(max_size)s
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
                await update.message.reply_text(response)
            else:
                await update.message.reply_text(f"متأسفانه هیچ موبایلی با صفحه نمایش {text} یافت نشد.")
        else:
            await update.message.reply_text("گزینه نامعتبر! لطفاً از منو استفاده کنید.")

    except Exception as e:
        logger.error(f"خطا در تابع handle_message: {e}")
        await update.message.reply_text("متأسفانه خطایی رخ داده است.")

async def start_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the review process"""
    user_id = update.effective_chat.id
    get_user_data(context, user_id)  # Initialize user data
    
    await update.message.reply_text(
        "لطفاً ایمیل خود را وارد کنید:"
    )
    return REVIEW_EMAIL

async def review_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email input"""
    user_id = update.effective_chat.id
    email = update.message.text
    
    if '@' not in email or '.' not in email:
        await update.message.reply_text("لطفاً یک ایمیل معتبر وارد کنید:")
        return REVIEW_EMAIL
    
    user_data = get_user_data(context, user_id)
    user_data['email'] = email
    
    await update.message.reply_text(
        "لطفاً شماره موبایل خود را وارد کنید:"
    )
    return REVIEW_PHONE

async def review_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone input"""
    user_id = update.effective_chat.id
    phone = update.message.text
    
    if not phone.isdigit() or len(phone) < 10:
        await update.message.reply_text("لطفاً یک شماره موبایل معتبر وارد کنید:")
        return REVIEW_PHONE
    
    user_data = get_user_data(context, user_id)
    user_data['phone'] = phone
    
    # Get list of mobiles for selection
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
        await update.message.reply_text("متأسفانه در حال حاضر هیچ موبایلی برای ثبت نظر موجود نیست.")
        return ConversationHandler.END
    
    keyboard = []
    for mobile in mobiles:
        keyboard.append([f"📱 {mobile['brand_name']} - {mobile['name']}"])
    keyboard.append(["❌ انصراف"])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(
        "لطفاً موبایل مورد نظر را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return REVIEW_MOBILE

async def review_mobile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mobile selection"""
    user_id = update.effective_chat.id
    text = update.message.text
    
    if text == "❌ انصراف":
        await update.message.reply_text(
            "ثبت نظر لغو شد.",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return ConversationHandler.END
    
    # Extract mobile ID from the selection
    query = """
    SELECT m.id 
    FROM mobiles m
    JOIN brands b ON m.brand_id = b.id
    WHERE CONCAT(b.name, ' - ', m.name) = %(mobile_name)s
    """
    mobile_name = text.replace("📱 ", "")
    mobile = execute_query(query, {'mobile_name': mobile_name})
    
    if not mobile:
        await update.message.reply_text("لطفاً یک موبایل معتبر انتخاب کنید:")
        return REVIEW_MOBILE
    
    user_data = get_user_data(context, user_id)
    user_data['mobile_id'] = mobile[0]['id']
    
    keyboard = [
        ["⭐", "⭐⭐", "⭐⭐⭐"],
        ["⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
        ["❌ انصراف"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(
        "لطفاً امتیاز خود را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return REVIEW_RATING

async def review_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle rating selection"""
    user_id = update.effective_chat.id
    text = update.message.text
    
    if text == "❌ انصراف":
        await update.message.reply_text(
            "ثبت نظر لغو شد.",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return ConversationHandler.END
    
    rating = len(text)
    if rating < 1 or rating > 5:
        await update.message.reply_text("لطفاً یک امتیاز معتبر انتخاب کنید:")
        return REVIEW_RATING
    
    user_data = get_user_data(context, user_id)
    user_data['rating'] = rating
    
    await update.message.reply_text(
        "لطفاً نظر خود را بنویسید:",
        reply_markup=ReplyKeyboardMarkup([["❌ انصراف"]], resize_keyboard=True)
    )
    return REVIEW_COMMENT

async def review_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle comment input and save the review"""
    user_id = update.effective_chat.id
    text = update.message.text
    
    if text == "❌ انصراف":
        await update.message.reply_text(
            "ثبت نظر لغو شد.",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return ConversationHandler.END
    
    user_data = get_user_data(context, user_id)
    
    try:
        # First check if the customer exists
        customer_query = """
        SELECT id FROM customers WHERE email = %(email)s
        """
        customer = execute_query(customer_query, {'email': user_data['email']})
        
        if not customer:
            # Create new customer
            create_customer_query = """
            INSERT INTO customers (email, name, phone) 
            VALUES (%(email)s, %(email)s, %(phone)s)
            RETURNING id
            """
            customer = execute_query(create_customer_query, {
                'email': user_data['email'],
                'phone': user_data['phone']
            })
        
        customer_id = customer[0]['id']
        
        # Add the review
        review_query = """
        INSERT INTO reviews (customer_id, mobile_id, rating, comment, review_date)
        VALUES (%(customer_id)s, %(mobile_id)s, %(rating)s, %(comment)s, CURRENT_TIMESTAMP)
        RETURNING id
        """
        review = execute_query(review_query, {
            'customer_id': customer_id,
            'mobile_id': user_data['mobile_id'],
            'rating': user_data['rating'],
            'comment': text
        })
        
        if review:
            await update.message.reply_text(
                "✅ نظر شما با موفقیت ثبت شد.",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "❌ خطا در ثبت نظر. لطفاً دوباره تلاش کنید.",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
            )
    except Exception as e:
        logger.error(f"Error adding review: {e}")
        await update.message.reply_text(
            "❌ خطا در ثبت نظر. لطفاً دوباره تلاش کنید.",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
    
    return ConversationHandler.END

async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the review process"""
    await update.message.reply_text(
        "ثبت نظر لغو شد.",
        reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
    )
    return ConversationHandler.END

async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the order process"""
    user_id = update.effective_chat.id
    get_user_data(context, user_id)  # Initialize user data
    
    await update.message.reply_text(
        "لطفاً ایمیل خود را وارد کنید:"
    )
    return ORDER_EMAIL

async def order_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email input for order"""
    user_id = update.effective_chat.id
    email = update.message.text
    
    if '@' not in email or '.' not in email:
        await update.message.reply_text("لطفاً یک ایمیل معتبر وارد کنید:")
        return ORDER_EMAIL
    
    user_data = get_user_data(context, user_id)
    user_data['email'] = email
    
    await update.message.reply_text(
        "لطفاً شماره موبایل خود را وارد کنید:"
    )
    return ORDER_PHONE

async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone input for order"""
    user_id = update.effective_chat.id
    phone = update.message.text
    
    if not phone.isdigit() or len(phone) < 10:
        await update.message.reply_text("لطفاً یک شماره موبایل معتبر وارد کنید:")
        return ORDER_PHONE
    
    user_data = get_user_data(context, user_id)
    user_data['phone'] = phone
    
    # Get list of available mobiles
    query = """
    SELECT 
        m.id,
        m.name,
        b.name as brand_name,
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
        await update.message.reply_text(
            "متأسفانه در حال حاضر هیچ موبایلی موجود نیست.",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return ConversationHandler.END
    
    keyboard = []
    for mobile in mobiles:
        keyboard.append([f"📱 {mobile['brand_name']} - {mobile['name']} ({mobile['price']:,.0f} تومان)"])
    keyboard.append(["❌ انصراف"])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(
        "لطفاً موبایل مورد نظر را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return ORDER_MOBILE

async def order_mobile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mobile selection for order"""
    user_id = update.effective_chat.id
    text = update.message.text
    
    if text == "❌ انصراف":
        await update.message.reply_text(
            "سفارش لغو شد.",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return ConversationHandler.END
    
    # Extract mobile ID from the selection
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
        await update.message.reply_text("لطفاً یک موبایل معتبر انتخاب کنید:")
        return ORDER_MOBILE
    
    user_data = get_user_data(context, user_id)
    user_data['mobile_id'] = mobile[0]['id']
    user_data['mobile_price'] = mobile[0]['price']
    user_data['available_quantity'] = mobile[0]['quantity']
    
    keyboard = []
    for i in range(1, min(6, mobile[0]['quantity'] + 1)):
        keyboard.append([str(i)])
    keyboard.append(["❌ انصراف"])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(
        f"لطفاً تعداد مورد نظر را انتخاب کنید (حداکثر {mobile[0]['quantity']}):",
        reply_markup=reply_markup
    )
    return ORDER_QUANTITY

async def order_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quantity selection for order"""
    user_id = update.effective_chat.id
    text = update.message.text
    
    if text == "❌ انصراف":
        await update.message.reply_text(
            "سفارش لغو شد.",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return ConversationHandler.END
    
    try:
        quantity = int(text)
        user_data = get_user_data(context, user_id)
        
        if quantity < 1 or quantity > user_data['available_quantity']:
            await update.message.reply_text(f"لطفاً یک عدد بین 1 تا {user_data['available_quantity']} وارد کنید:")
            return ORDER_QUANTITY
        
        user_data['quantity'] = quantity
        total_price = quantity * user_data['mobile_price']
        
        # Get mobile details for confirmation
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
        keyboard = [
            ["✅ تأیید سفارش"],
            ["❌ انصراف"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
        return ORDER_CONFIRM
        
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد معتبر وارد کنید:")
        return ORDER_QUANTITY

async def order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle order confirmation"""
    user_id = update.effective_chat.id
    text = update.message.text
    
    if text == "❌ انصراف":
        await update.message.reply_text(
            "سفارش لغو شد.",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return ConversationHandler.END
    
    if text != "✅ تأیید سفارش":
        await update.message.reply_text("لطفاً تأیید یا انصراف را انتخاب کنید:")
        return ORDER_CONFIRM
    
    user_data = get_user_data(context, user_id)
    
    try:
        # Create order
        order_items = [{
            'mobile_id': user_data['mobile_id'],
            'quantity': user_data['quantity'],
            'price': user_data['mobile_price']
        }]
        
        customer_info = {
            'email': user_data['email'],
            'phone': user_data['phone'],
            'name': user_data['email']  # Using email as name for now
        }
        
        order_id = create_order(customer_info, order_items)
        
        if order_id:
            await update.message.reply_text(
                f"✅ سفارش شما با موفقیت ثبت شد.\nشماره سفارش: {order_id}",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "❌ خطا در ثبت سفارش. لطفاً دوباره تلاش کنید.",
                reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
            )
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        await update.message.reply_text(
            "❌ خطا در ثبت سفارش. لطفاً دوباره تلاش کنید.",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
    
    return ConversationHandler.END

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the order process"""
    await update.message.reply_text(
        "سفارش لغو شد.",
        reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
    )
    return ConversationHandler.END

async def start_order_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the order list process"""
    keyboard = [
        ["📧 جستجو با ایمیل", "📱 جستجو با شماره تماس"],
        ["🔙 بازگشت"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(
        "لطفاً روش جستجوی سفارشات را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return ORDER_LIST_EMAIL

async def order_list_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email input for order list"""
    text = update.message.text
    
    if text == "🔙 بازگشت":
        keyboard = [
            ["🛒 سفارش جدید", "📋 لیست سفارشات"],
            ["🔙 بازگشت"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)
        return ConversationHandler.END
    
    if text == "📧 جستجو با ایمیل":
        await update.message.reply_text(
            "لطفاً ایمیل خود را وارد کنید:",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return ORDER_LIST_EMAIL
    
    if text == "📱 جستجو با شماره تماس":
        await update.message.reply_text(
            "لطفاً شماره تماس خود را وارد کنید:",
            reply_markup=ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)
        )
        return ORDER_LIST_PHONE
    
    # Validate email format
    if '@' not in text or '.' not in text:
        await update.message.reply_text("لطفاً یک ایمیل معتبر وارد کنید:")
        return ORDER_LIST_EMAIL
    
    # Get orders by email
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
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("هیچ سفارشی با این ایمیل یافت نشد.")
    
    keyboard = [
        ["🛒 سفارش جدید", "📋 لیست سفارشات"],
        ["🔙 بازگشت"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)
    return ConversationHandler.END

async def order_list_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone input for order list"""
    text = update.message.text
    
    if text == "🔙 بازگشت":
        keyboard = [
            ["🛒 سفارش جدید", "📋 لیست سفارشات"],
            ["🔙 بازگشت"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)
        return ConversationHandler.END
    
    # Validate phone number
    if not text.isdigit() or len(text) < 10:
        await update.message.reply_text("لطفاً یک شماره تماس معتبر وارد کنید:")
        return ORDER_LIST_PHONE
    
    # Get orders by phone
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
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("هیچ سفارشی با این شماره تماس یافت نشد.")
    
    keyboard = [
        ["🛒 سفارش جدید", "📋 لیست سفارشات"],
        ["🔙 بازگشت"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)
    return ConversationHandler.END

def main():
    try:
        TOKEN = '8006495662:AAF13gqftEJeGYvrPRmNhwYgaHrYs95Pv-s'
        # تنظیم پراکسی SOCKS5
        from telegram.request import HTTPXRequest
        request = HTTPXRequest(proxy="socks5://127.0.0.1:1080")
        
        # ساخت Application با پراکسی
        app = Application.builder().token(TOKEN).http_request(request).build()
        # Add conversation handlers
        review_conv_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^✍️ نظر بده$"), start_review)],
            states={
                REVIEW_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_email)],
                REVIEW_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_phone)],
                REVIEW_MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_mobile)],
                REVIEW_RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_rating)],
                REVIEW_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_comment)],
            },
            fallbacks=[MessageHandler(filters.Regex("^❌ انصراف$"), cancel_review)]
        )
        
        order_conv_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^🛒 سفارش جدید$"), start_order)],
            states={
                ORDER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_email)],
                ORDER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_phone)],
                ORDER_MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_mobile)],
                ORDER_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_quantity)],
                ORDER_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_confirm)],
            },
            fallbacks=[MessageHandler(filters.Regex("^❌ انصراف$"), cancel_order)]
        )
        
        order_list_conv_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^📋 لیست سفارشات$"), start_order_list)],
            states={
                ORDER_LIST_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_list_email)],
                ORDER_LIST_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_list_phone)],
            },
            fallbacks=[MessageHandler(filters.Regex("^🔙 بازگشت$"), cancel_order)]
        )
        
        app.add_handler(CommandHandler('start', start))
        app.add_handler(review_conv_handler)
        app.add_handler(order_conv_handler)
        app.add_handler(order_list_conv_handler)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Starting bot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()