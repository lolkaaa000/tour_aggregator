-- Цены и поведение пользователей

-- Средняя цена туров по неделям
SELECT strftime('%Y-W%W', t.departure_date) AS week,
       COUNT(*) AS tour_count,
       ROUND(AVG(t.actual_price), 0) AS avg_price,
       ROUND(MIN(t.actual_price), 0) AS min_price,
       ROUND(MAX(t.actual_price), 0) AS max_price
FROM tours t
WHERE t.is_available = 1
GROUP BY week
ORDER BY week;

-- Историческая цена конкретного тура
SELECT ph.tour_id, ph.price, ph.recorded_at,
       t.actual_price AS current_price
FROM price_history ph
JOIN tours t ON ph.tour_id = t.id
ORDER BY ph.tour_id, ph.recorded_at;

-- Среднемесячные цены по странам
SELECT c.name AS country,
       strftime('%m', t.departure_date) AS month,
       COUNT(*) AS tour_count,
       ROUND(AVG(t.actual_price), 0) AS avg_price
FROM tours t
JOIN countries c ON t.country_id = c.id
WHERE t.is_available = 1
GROUP BY c.name, month
ORDER BY country, month;

-- Цена за ночь по странам
SELECT c.name AS country,
       ROUND(AVG(t.actual_price / t.duration_nights), 0) AS avg_price_per_night,
       ROUND(AVG(t.actual_price / t.duration_nights / t.adults), 0) AS avg_price_per_person_night
FROM tours t
JOIN countries c ON t.country_id = c.id
WHERE t.is_available = 1
GROUP BY c.name
ORDER BY avg_price_per_night ASC;

-- Аномалии цен

-- Ценовые аномалии (z-score > 2)
WITH tour_stats AS (
    SELECT country_id,
           AVG(actual_price) AS mean_price,
           SQRT(AVG(actual_price * actual_price) - AVG(actual_price) * AVG(actual_price)) AS stddev_price
    FROM tours
    WHERE is_available = 1
    GROUP BY country_id
    HAVING stddev_price > 0
),
tour_zscore AS (
    SELECT t.id, t.country_id, t.actual_price,
           ts.mean_price, ts.stddev_price,
           (t.actual_price - ts.mean_price) / ts.stddev_price AS z_score
    FROM tours t
    JOIN tour_stats ts ON t.country_id = ts.country_id
    WHERE t.is_available = 1
)
SELECT z.country_id, c.name AS country, z.id AS tour_id,
       h.name AS hotel, z.actual_price,
       ROUND(z.mean_price, 0) AS mean_price,
       ROUND(z.z_score, 2) AS z_score,
       CASE
           WHEN z.z_score > 2 THEN 'ANOMALY_HIGH'
           WHEN z.z_score < -2 THEN 'ANOMALY_LOW'
           ELSE 'NORMAL'
       END AS status
FROM tour_zscore z
JOIN countries c ON z.country_id = c.id
JOIN tours t ON z.id = t.id
JOIN hotels h ON t.hotel_id = h.id
WHERE ABS(z.z_score) > 2
ORDER BY ABS(z.z_score) DESC
LIMIT 30;

-- Разница цен в одном курорте
SELECT r.name AS resort, c.name AS country,
       MAX(t.actual_price) - MIN(t.actual_price) AS price_spread,
       ROUND(AVG(t.actual_price), 0) AS avg_price,
       COUNT(DISTINCT h.id) AS hotel_count
FROM tours t
JOIN hotels h ON t.hotel_id = h.id
JOIN resorts r ON h.resort_id = r.id
JOIN countries c ON r.country_id = c.id
WHERE t.is_available = 1
GROUP BY r.name, c.name
HAVING hotel_count > 3
ORDER BY price_spread DESC
LIMIT 20;

-- Туры с максимальной скидкой
SELECT c.name AS country, h.name AS hotel,
       t.original_price, t.actual_price,
       t.discount_pct,
       ROUND(t.original_price - t.actual_price, 0) AS discount_amount
FROM tours t
JOIN countries c ON t.country_id = c.id
JOIN hotels h ON t.hotel_id = h.id
WHERE t.discount_pct > 0 AND t.is_available = 1
ORDER BY t.discount_pct DESC
LIMIT 20;

-- Поведение пользователей

-- Воронка конверсии: Поиск → Просмотр → Клик → Бронь
WITH funnel AS (
    SELECT
        (SELECT COUNT(DISTINCT session_id) FROM search_logs) AS searches,
        (SELECT COUNT(DISTINCT session_id) FROM tour_views) AS views,
        (SELECT COUNT(DISTINCT session_id) FROM click_logs) AS clicks,
        (SELECT COUNT(DISTINCT b.session_id) FROM bookings b
         JOIN click_logs cl ON cl.session_id = b.session_id
         WHERE b.session_id IS NOT NULL
        ) AS bookings_via_click
)
SELECT searches,
       views,
       clicks,
       bookings_via_click AS bookings,
       ROUND(views * 100.0 / NULLIF(searches, 0), 1) AS search_to_view_pct,
       ROUND(clicks * 100.0 / NULLIF(views, 0), 1) AS view_to_click_pct,
       ROUND(bookings_via_click * 100.0 / NULLIF(searches, 0), 1) AS search_to_book_pct
FROM funnel;

-- Конверсия по странам
SELECT c.name AS country,
       COUNT(DISTINCT sl.session_id) AS searches,
       COUNT(DISTINCT b.id) AS bookings,
       ROUND(COUNT(DISTINCT b.id) * 100.0 / NULLIF(COUNT(DISTINCT sl.session_id), 0), 1) AS conversion_pct
FROM search_logs sl
JOIN countries c ON sl.country_id = c.id
LEFT JOIN bookings b ON b.tour_id IN (
    SELECT t.id FROM tours t WHERE t.country_id = c.id
)
GROUP BY c.name
ORDER BY conversion_pct DESC;

-- Популярные направления: поиск vs бронь
SELECT c.name AS country,
       COUNT(DISTINCT sl.session_id) AS search_sessions,
       (SELECT COUNT(*) FROM bookings b
        JOIN tours t ON b.tour_id = t.id
        WHERE t.country_id = c.id) AS booking_count,
       ROUND((SELECT COUNT(*) FROM bookings b
        JOIN tours t ON b.tour_id = t.id
        WHERE t.country_id = c.id) * 100.0 / NULLIF(COUNT(DISTINCT sl.session_id), 0), 1) AS search_to_book_pct
FROM search_logs sl
JOIN countries c ON sl.country_id = c.id
GROUP BY c.name
ORDER BY search_sessions DESC;

-- Отказы по сессиям
WITH view_counts AS (
    SELECT session_id, COUNT(*) AS view_count
    FROM tour_views
    GROUP BY session_id
),
click_sessions AS (
    SELECT DISTINCT session_id FROM click_logs
)
SELECT
    (SELECT COUNT(DISTINCT session_id) FROM search_logs) AS total_search_sessions,
    (SELECT COUNT(*) FROM view_counts WHERE view_count = 1) AS single_view_sessions,
    (SELECT COUNT(*) FROM view_counts vc
     WHERE vc.session_id NOT IN (SELECT session_id FROM click_sessions)) AS no_click_sessions,
    ROUND((SELECT COUNT(*) FROM view_counts WHERE view_count = 1) * 100.0
          / NULLIF((SELECT COUNT(DISTINCT session_id) FROM search_logs), 0), 1) AS bounce_rate_pct;

-- Среднее время просмотра перед кликом
SELECT
    ROUND(AVG(tv.view_duration), 0) AS avg_view_duration_seconds,
    ROUND(AVG(tv.view_duration) / 60.0, 1) AS avg_view_duration_minutes
FROM tour_views tv
JOIN click_logs cl ON tv.session_id = cl.session_id AND tv.tour_id = cl.tour_id;

-- Статус бронирований
SELECT status,
       COUNT(*) AS count,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM bookings), 1) AS pct,
       ROUND(AVG(total_price), 0) AS avg_price
FROM bookings
GROUP BY status
ORDER BY count DESC;

-- Повторные покупки
SELECT u.id AS user_id, u.username, u.city,
       COUNT(b.id) AS booking_count,
       ROUND(SUM(b.total_price), 0) AS total_spent
FROM users u
JOIN bookings b ON u.id = b.user_id
GROUP BY u.id
HAVING booking_count > 1
ORDER BY booking_count DESC, total_spent DESC
LIMIT 20;
