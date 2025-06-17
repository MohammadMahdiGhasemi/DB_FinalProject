-- 📱 نمایش موبایل‌ها (Show Mobiles)
-- Complex query to show all mobiles with their specifications, brand, and average rating
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
ORDER BY average_rating DESC, review_count DESC;

-- 🔍 جستجوی پیشرفته (Advanced Search)
-- 📱 بر اساس برند (By Brand)
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
WHERE b.name = :brand_name
GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
ORDER BY average_rating DESC, review_count DESC;

-- 💰 بر اساس قیمت (By Price)
-- For price range "تا 5 میلیون" (Up to 5 million)
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
WHERE m.price <= 5000000
GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
ORDER BY m.price ASC;

-- Similar queries for other price ranges...

-- ⚙️ بر اساس مشخصات (By Specifications)
-- For RAM search
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
JOIN specifications s ON m.id = s.mobile_id
LEFT JOIN reviews r ON m.id = r.mobile_id
LEFT JOIN images i ON m.id = i.mobile_id
WHERE s.ram = :ram_value
GROUP BY m.id, m.name, b.name, m.price, s.ram, s.storage, s.processor, s.screen_size, s.battery_capacity, s.camera
ORDER BY average_rating DESC;

-- 🛒 سفارش جدید (New Order)
-- Query to insert new order with transaction
BEGIN;
    -- Insert customer if not exists
    INSERT INTO customers (name, email, phone)
    VALUES (:name, :email, :phone)
    ON CONFLICT (email) DO UPDATE 
    SET name = EXCLUDED.name, phone = EXCLUDED.phone
    RETURNING id INTO :customer_id;

    -- Insert order
    INSERT INTO orders (customer_id, total_price)
    VALUES (:customer_id, :total_price)
    RETURNING id INTO :order_id;

    -- Insert order items
    INSERT INTO order_items (order_id, mobile_id, quantity, price)
    SELECT 
        :order_id,
        mobile_id,
        quantity,
        price
    FROM unnest(:mobile_ids, :quantities, :prices) AS t(mobile_id, quantity, price);

    -- Update stock
    UPDATE stock
    SET quantity = quantity - t.quantity
    FROM unnest(:mobile_ids, :quantities) AS t(mobile_id, quantity)
    WHERE stock.mobile_id = t.mobile_id;
COMMIT;

-- ⭐ نظرات کاربران (User Reviews)
-- Complex query to show reviews with customer and mobile details
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
ORDER BY r.review_date DESC, helpful_votes DESC;

-- 📋 موجودی مغازه‌ها (Store Inventory)
-- Complex query to show inventory with seller and mobile details
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
ORDER BY s.quantity DESC, total_sold DESC;

-- 🔥 پیشنهاد ویژه (Special Offers)
-- Complex query to show popular and highly rated mobiles
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
ORDER BY purchase_count DESC, average_rating DESC;

-- ✍️ نظر بده (Give Review)
-- Query to insert new review
INSERT INTO reviews (customer_id, mobile_id, rating, comment)
VALUES (
    (SELECT id FROM customers WHERE email = :email),
    :mobile_id,
    :rating,
    :comment
)
RETURNING id;

-- Additional complex queries for analytics
-- Most popular brands
SELECT 
    b.name AS brand_name,
    COUNT(DISTINCT m.id) AS total_models,
    COUNT(DISTINCT oi.id) AS total_sales,
    COALESCE(AVG(r.rating), 0) AS average_rating,
    SUM(oi.quantity * oi.price) AS total_revenue
FROM brands b
JOIN mobiles m ON b.id = m.brand_id
LEFT JOIN order_items oi ON m.id = oi.mobile_id
LEFT JOIN reviews r ON m.id = r.mobile_id
GROUP BY b.name
ORDER BY total_sales DESC, average_rating DESC;

-- Customer purchase history with recommendations
WITH customer_purchases AS (
    SELECT 
        c.id AS customer_id,
        c.name AS customer_name,
        m.brand_id,
        COUNT(DISTINCT oi.id) AS purchase_count,
        AVG(r.rating) AS average_rating
    FROM customers c
    JOIN orders o ON c.id = o.customer_id
    JOIN order_items oi ON o.id = oi.order_id
    JOIN mobiles m ON oi.mobile_id = m.id
    LEFT JOIN reviews r ON m.id = r.mobile_id AND c.id = r.customer_id
    GROUP BY c.id, c.name, m.brand_id
)
SELECT 
    cp.customer_name,
    b.name AS preferred_brand,
    cp.purchase_count,
    cp.average_rating,
    STRING_AGG(DISTINCT m.name, ', ') AS recommended_mobiles
FROM customer_purchases cp
JOIN brands b ON cp.brand_id = b.id
LEFT JOIN mobiles m ON b.id = m.brand_id
LEFT JOIN order_items oi ON m.id = oi.mobile_id
WHERE m.id NOT IN (
    SELECT mobile_id 
    FROM order_items oi2 
    JOIN orders o2 ON oi2.order_id = o2.id 
    WHERE o2.customer_id = cp.customer_id
)
GROUP BY cp.customer_name, b.name, cp.purchase_count, cp.average_rating
ORDER BY cp.purchase_count DESC, cp.average_rating DESC; 