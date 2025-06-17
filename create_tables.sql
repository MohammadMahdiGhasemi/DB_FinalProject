-- ایجاد جدول برندها
CREATE TABLE IF NOT EXISTS brands (
    id SERIAL PRIMARY KEY,
    brand_name VARCHAR(50) NOT NULL UNIQUE
);

-- ایجاد جدول موبایل‌ها
CREATE TABLE IF NOT EXISTS mobiles (
    id SERIAL PRIMARY KEY,
    mobile_name VARCHAR(100) NOT NULL,
    brand_id INTEGER REFERENCES brands(id),
    price DECIMAL(12,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ایجاد جدول مشخصات فنی
CREATE TABLE IF NOT EXISTS specifications (
    mobile_id INTEGER PRIMARY KEY REFERENCES mobiles(id),
    ram INTEGER NOT NULL,
    storage INTEGER NOT NULL,
    processor VARCHAR(100) NOT NULL,
    screen_size DECIMAL(4,2) NOT NULL,
    battery_capacity INTEGER NOT NULL,
    camera INTEGER NOT NULL
);

-- ایجاد جدول تصاویر
CREATE TABLE IF NOT EXISTS images (
    id SERIAL PRIMARY KEY,
    mobile_id INTEGER REFERENCES mobiles(id),
    image_url TEXT NOT NULL
);

-- ایجاد جدول مشتریان
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ایجاد جدول سفارشات
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    total_price DECIMAL(12,2) NOT NULL,
    discount_code VARCHAR(20),
    discount_amount DECIMAL(12,2) DEFAULT 0,
    final_price DECIMAL(12,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ایجاد جدول آیتم‌های سفارش
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    mobile_id INTEGER REFERENCES mobiles(id),
    quantity INTEGER NOT NULL,
    price DECIMAL(12,2) NOT NULL
);

-- ایجاد جدول نظرات
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    mobile_id INTEGER REFERENCES mobiles(id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ایجاد جدول تخفیف‌ها
CREATE TABLE IF NOT EXISTS discounts (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    discount_percent INTEGER NOT NULL CHECK (discount_percent > 0 AND discount_percent <= 100),
    is_active BOOLEAN DEFAULT true,
    expiry_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ایجاد جدول موجودی
CREATE TABLE IF NOT EXISTS stock (
    mobile_id INTEGER PRIMARY KEY REFERENCES mobiles(id),
    quantity INTEGER NOT NULL DEFAULT 0
);

-- ایجاد ویو برای نمایش موبایل‌ها با برند
CREATE OR REPLACE VIEW view_mobile_brands AS
SELECT 
    m.id as mobile_id,
    m.mobile_name,
    b.brand_name,
    m.price
FROM mobiles m
JOIN brands b ON m.brand_id = b.id;

-- ایجاد ویو برای نمایش نظرات با امتیاز بالای 3
CREATE OR REPLACE VIEW view_reviews_above_3 AS
SELECT 
    r.id as review_id,
    c.name as customer_name,
    m.mobile_name,
    r.rating,
    r.comment
FROM reviews r
JOIN customers c ON r.customer_id = c.id
JOIN mobiles m ON r.mobile_id = m.id
WHERE r.rating > 3;

-- ایجاد ویو برای نمایش موجودی هر فروشنده
CREATE OR REPLACE VIEW view_stock_per_seller AS
SELECT 
    m.id as seller_id,
    b.brand_name as seller_name,
    SUM(s.quantity) as total_stock
FROM mobiles m
JOIN brands b ON m.brand_id = b.id
JOIN stock s ON m.id = s.mobile_id
GROUP BY m.id, b.brand_name;

-- ایجاد ویو برای نمایش موبایل‌های محبوب
CREATE OR REPLACE VIEW view_popular_mobiles AS
SELECT 
    m.id as mobile_id,
    m.mobile_name,
    COUNT(oi.id) as purchase_count
FROM mobiles m
JOIN order_items oi ON m.id = oi.mobile_id
GROUP BY m.id, m.mobile_name
ORDER BY purchase_count DESC;

-- درج داده‌های نمونه
INSERT INTO brands (brand_name) VALUES 
('Samsung'),
('Apple'),
('Xiaomi'),
('Huawei'),
('Nokia')
ON CONFLICT (brand_name) DO NOTHING;

-- درج موبایل‌های نمونه
INSERT INTO mobiles (mobile_name, brand_id, price) VALUES 
('Galaxy S21', 1, 25000000),
('iPhone 13', 2, 35000000),
('Mi 11', 3, 15000000),
('P40 Pro', 4, 20000000),
('8.3', 5, 12000000)
ON CONFLICT DO NOTHING;

-- درج مشخصات فنی نمونه
INSERT INTO specifications (mobile_id, ram, storage, processor, screen_size, battery_capacity, camera) VALUES 
(1, 8, 128, 'Snapdragon 888', 6.2, 4000, 64),
(2, 6, 128, 'A15 Bionic', 6.1, 3240, 12),
(3, 8, 256, 'Snapdragon 888', 6.81, 4600, 108),
(4, 8, 256, 'Kirin 990', 6.58, 4200, 50),
(5, 8, 128, 'Snapdragon 765G', 6.81, 4500, 64)
ON CONFLICT (mobile_id) DO NOTHING;

-- درج کدهای تخفیف نمونه
INSERT INTO discounts (code, discount_percent, expiry_date) VALUES 
('WELCOME10', 10, CURRENT_TIMESTAMP + INTERVAL '30 days'),
('SUMMER20', 20, CURRENT_TIMESTAMP + INTERVAL '15 days'),
('SPECIAL15', 15, CURRENT_TIMESTAMP + INTERVAL '7 days')
ON CONFLICT (code) DO NOTHING;

-- درج موجودی نمونه
INSERT INTO stock (mobile_id, quantity) VALUES 
(1, 10),
(2, 5),
(3, 15),
(4, 8),
(5, 12)
ON CONFLICT (mobile_id) DO NOTHING; 