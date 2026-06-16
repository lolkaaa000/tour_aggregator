-- Аналитика: фильтрация и агрегация

-- Фильтрация по стране/направлению

-- Туры в Турцию с ценами
SELECT t.id, c.name AS country, r.name AS resort, h.name AS hotel,
       h.star_rating, t.departure_date, t.duration_nights,
       t.meal_type, t.actual_price, op.short_name AS operator
FROM tours t
JOIN countries c ON t.country_id = c.id
JOIN resorts r ON t.resort_id = r.id
JOIN hotels h ON t.hotel_id = h.id
JOIN tour_operators op ON t.operator_id = op.id
WHERE c.name = 'Турция' AND t.is_available = 1
ORDER BY t.actual_price ASC
LIMIT 20;

-- Топ-10 курортов по количеству туров
SELECT c.name AS country, r.name AS resort,
       COUNT(*) AS tour_count,
       ROUND(AVG(t.actual_price), 0) AS avg_price,
       ROUND(MIN(t.actual_price), 0) AS min_price,
       ROUND(MAX(t.actual_price), 0) AS max_price
FROM tours t
JOIN countries c ON t.country_id = c.id
JOIN resorts r ON t.resort_id = r.id
WHERE t.is_available = 1
GROUP BY c.name, r.name
ORDER BY tour_count DESC
LIMIT 10;

-- Туры по выбранному курорту
SELECT t.id, h.name AS hotel, h.star_rating, t.departure_date,
       t.duration_nights, t.meal_type, t.actual_price,
       op.short_name AS operator, t.room_type
FROM tours t
JOIN hotels h ON t.hotel_id = h.id
JOIN tour_operators op ON t.operator_id = op.id
JOIN resorts r ON t.resort_id = r.id
WHERE r.name = 'Анталья' AND t.is_available = 1
ORDER BY t.actual_price ASC
LIMIT 30;

-- Фильтрация по дате вылета

-- Туры на ближайшие 2 недели
SELECT c.name AS country, r.name AS resort, h.name AS hotel,
       t.departure_date, t.duration_nights, t.actual_price,
       op.short_name AS operator
FROM tours t
JOIN countries c ON t.country_id = c.id
JOIN resorts r ON t.resort_id = r.id
JOIN hotels h ON t.hotel_id = h.id
JOIN tour_operators op ON t.operator_id = op.id
WHERE t.departure_date BETWEEN date('now') AND date('now', '+14 days')
  AND t.is_available = 1
ORDER BY t.departure_date, t.actual_price ASC;

-- Туры по месяцам
SELECT strftime('%Y-%m', t.departure_date) AS month,
       COUNT(*) AS tour_count,
       ROUND(AVG(t.actual_price), 0) AS avg_price,
       ROUND(MIN(t.actual_price), 0) AS min_price,
       ROUND(MAX(t.actual_price), 0) AS max_price
FROM tours t
WHERE t.is_available = 1
GROUP BY strftime('%Y-%m', t.departure_date)
ORDER BY month;

-- Горящие туры
SELECT c.name AS country, h.name AS hotel, t.departure_date,
       t.duration_nights, t.actual_price, t.original_price,
       t.discount_pct, op.short_name AS operator
FROM tours t
JOIN countries c ON t.country_id = c.id
JOIN hotels h ON t.hotel_id = h.id
JOIN tour_operators op ON t.operator_id = op.id
WHERE t.departure_date BETWEEN date('now') AND date('now', '+7 days')
  AND t.discount_pct > 3
  AND t.is_available = 1
ORDER BY t.discount_pct DESC;

-- Фильтрация по цене

-- Распределение по ценовым диапазонам
SELECT
    CASE
        WHEN t.actual_price < 40000 THEN 'до 40 000'
        WHEN t.actual_price < 60000 THEN '40 000 - 60 000'
        WHEN t.actual_price < 80000 THEN '60 000 - 80 000'
        WHEN t.actual_price < 100000 THEN '80 000 - 100 000'
        WHEN t.actual_price < 150000 THEN '100 000 - 150 000'
        WHEN t.actual_price < 200000 THEN '150 000 - 200 000'
        ELSE '200 000+'
    END AS price_range,
    COUNT(*) AS tour_count,
    ROUND(AVG(t.actual_price), 0) AS avg_price,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM tours WHERE is_available = 1), 1) AS pct
FROM tours t
WHERE t.is_available = 1
GROUP BY price_range
ORDER BY MIN(t.actual_price);

-- Лучшие предложения по цене/качеству
SELECT c.name AS country, r.name AS resort, h.name AS hotel,
       h.star_rating, t.actual_price,
       ROUND(t.actual_price / t.duration_nights, 0) AS price_per_night,
       t.meal_type, t.departure_date, op.short_name AS operator
FROM tours t
JOIN countries c ON t.country_id = c.id
JOIN resorts r ON t.resort_id = r.id
JOIN hotels h ON t.hotel_id = h.id
JOIN tour_operators op ON t.operator_id = op.id
WHERE t.is_available = 1 AND h.star_rating >= 4
ORDER BY price_per_night ASC
LIMIT 20;

-- Дешевле заданной цены по стране
SELECT c.name AS country, h.name AS hotel, h.star_rating,
       t.actual_price, t.departure_date, t.duration_nights,
       t.meal_type, op.short_name AS operator
FROM tours t
JOIN countries c ON t.country_id = c.id
JOIN hotels h ON t.hotel_id = h.id
JOIN tour_operators op ON t.operator_id = op.id
WHERE t.actual_price <= 80000
  AND c.name = 'Турция'
  AND t.is_available = 1
ORDER BY t.actual_price ASC
LIMIT 20;

-- Сравнение операторов

-- Рыночная доля операторов
SELECT op.short_name AS operator,
       COUNT(*) AS tour_count,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM tours WHERE is_available = 1), 1) AS market_share_pct,
       ROUND(AVG(t.actual_price), 0) AS avg_price,
       ROUND(MIN(t.actual_price), 0) AS min_price,
       ROUND(MAX(t.actual_price), 0) AS max_price
FROM tours t
JOIN tour_operators op ON t.operator_id = op.id
WHERE t.is_available = 1
GROUP BY op.short_name
ORDER BY tour_count DESC;

-- Средняя цена по операторам и странам
SELECT op.short_name AS operator, c.name AS country,
       COUNT(*) AS tours,
       ROUND(AVG(t.actual_price), 0) AS avg_price
FROM tours t
JOIN tour_operators op ON t.operator_id = op.id
JOIN countries c ON t.country_id = c.id
WHERE t.is_available = 1
GROUP BY op.short_name, c.name
ORDER BY country, avg_price;

-- Оператор с лучшей ценой для конкретного отеля
SELECT h.name AS hotel, op.short_name AS operator,
       t.actual_price, t.departure_date, t.meal_type
FROM tours t
JOIN hotels h ON t.hotel_id = h.id
JOIN tour_operators op ON t.operator_id = op.id
WHERE t.is_available = 1
  AND t.id IN (
    SELECT t2.id FROM tours t2
    WHERE t2.hotel_id = t.hotel_id
      AND t2.departure_date = t.departure_date
      AND t2.is_available = 1
    ORDER BY t2.actual_price ASC
    LIMIT 1
  )
ORDER BY h.name
LIMIT 20;

-- Агрегированные метрики

-- Общая статистика по базе
SELECT
    (SELECT COUNT(*) FROM tours WHERE is_available = 1) AS active_tours,
    (SELECT COUNT(*) FROM hotels) AS total_hotels,
    (SELECT COUNT(DISTINCT country_id) FROM tours) AS countries_with_tours,
    (SELECT ROUND(AVG(actual_price), 0) FROM tours WHERE is_available = 1) AS avg_tour_price,
    (SELECT ROUND(MIN(actual_price), 0) FROM tours WHERE is_available = 1) AS min_tour_price,
    (SELECT ROUND(MAX(actual_price), 0) FROM tours WHERE is_available = 1) AS max_tour_price,
    (SELECT COUNT(*) FROM bookings) AS total_bookings,
    (SELECT COUNT(DISTINCT user_id) FROM bookings) AS unique_buyers;

-- Статистика по странам
SELECT c.name AS country,
       COUNT(*) AS tour_count,
       COUNT(DISTINCT r.id) AS resort_count,
       COUNT(DISTINCT h.id) AS hotel_count,
       ROUND(AVG(t.actual_price), 0) AS avg_price,
       ROUND(AVG(t.duration_nights), 1) AS avg_nights
FROM tours t
JOIN countries c ON t.country_id = c.id
JOIN resorts r ON t.resort_id = r.id
JOIN hotels h ON t.hotel_id = h.id
WHERE t.is_available = 1
GROUP BY c.name
ORDER BY tour_count DESC;

-- Средний рейтинг отелей по странам
SELECT c.name AS country,
       COUNT(h.id) AS hotel_count,
       ROUND(AVG(h.star_rating), 1) AS avg_stars,
       SUM(CASE WHEN h.star_rating = 5 THEN 1 ELSE 0 END) AS five_star_count,
       SUM(CASE WHEN h.star_rating = 4 THEN 1 ELSE 0 END) AS four_star_count
FROM hotels h
JOIN resorts r ON h.resort_id = r.id
JOIN countries c ON r.country_id = c.id
GROUP BY c.name
ORDER BY avg_stars DESC;
