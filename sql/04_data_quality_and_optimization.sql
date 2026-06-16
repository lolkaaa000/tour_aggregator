-- ============================================================
-- КАЧЕСТВО ДАННЫХ И ОПТИМИЗАЦИЯ
-- ============================================================

-- ============================================================
-- РАЗДЕЛ 1: АКТУАЛЬНОСТЬ ДАННЫХ
-- ============================================================

-- 1.1 Устаревшие туры (дата вылета уже прошла)
SELECT COUNT(*) AS outdated_tours
FROM tours
WHERE departure_date < date('now') AND is_available = 1;

-- 1.2 Доля актуальных туров
SELECT
    COUNT(*) AS total_tours,
    SUM(CASE WHEN departure_date >= date('now') THEN 1 ELSE 0 END) AS current_tours,
    ROUND(SUM(CASE WHEN departure_date >= date('now') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS current_pct
FROM tours;

-- 1.3 Давность последнего обновления туров по операторам
SELECT op.short_name AS operator,
       COUNT(*) AS tour_count,
       MAX(t.updated_at) AS last_updated,
       ROUND((julianday('now') - julianday(MAX(t.updated_at))), 1) AS days_since_update
FROM tours t
JOIN tour_operators op ON t.operator_id = op.id
GROUP BY op.short_name
ORDER BY days_since_update DESC;

-- ============================================================
-- РАЗДЕЛ 2: АУДИТ ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ
-- ============================================================

-- 2.1 Туры без цены
SELECT COUNT(*) AS tours_no_price FROM tours WHERE actual_price IS NULL OR actual_price = 0;

-- 2.2 Туры без даты вылета
SELECT COUNT(*) AS tours_no_date FROM tours WHERE departure_date IS NULL OR departure_date = '';

-- 2.3 Отели без курорта
SELECT COUNT(*) AS hotels_no_resort FROM hotels WHERE resort_id IS NULL;

-- 2.4 Туры без оператора
SELECT COUNT(*) AS tours_no_operator FROM tours WHERE operator_id IS NULL;

-- 2.5 Сырые записи без маппинга
SELECT 'hotels_raw' AS tbl, COUNT(*) AS unprocessed FROM hotels_raw WHERE is_processed = 0
UNION ALL
SELECT 'tours_raw', COUNT(*) FROM tours_raw WHERE is_processed = 0;

-- ============================================================
-- РАЗДЕЛ 3: ЛОГИЧЕСКАЯ ЦЕЛОСТНОСТЬ
-- ============================================================

-- 3.1 Туры с отрицательной ценой
SELECT id, actual_price, hotel_id, operator_id
FROM tours WHERE actual_price < 0;

-- 3.2 Туры с нулевой длительностью
SELECT id, duration_nights, actual_price
FROM tours WHERE duration_nights <= 0;

-- 3.3 Отели со звёздностью вне диапазона [2, 5]
SELECT id, name, star_rating
FROM hotels WHERE star_rating < 2 OR star_rating > 5;

-- 3.4 Туры с нереалистичным числом гостей
SELECT id, adults, children, actual_price
FROM tours WHERE adults < 1 OR adults > 6 OR children < 0 OR children > 4;

-- 3.5 Бронирования с ценой 0 или отрицательной
SELECT id, user_id, total_price, status
FROM bookings WHERE total_price <= 0;

-- 3.6 Даты заезда позже даты бронирования (логическая ошибка)
SELECT b.id, b.booking_date, t.departure_date
FROM bookings b
JOIN tours t ON b.tour_id = t.id
WHERE t.departure_date < b.booking_date;

-- ============================================================
-- РАЗДЕЛ 4: ЦЕЛОСТНОСТЬ ВНЕШНИХ КЛЮЧЕЙ
-- ============================================================

-- 4.1 Туры со ссылками на несуществующие отели
SELECT t.id, t.hotel_id
FROM tours t
LEFT JOIN hotels h ON t.hotel_id = h.id
WHERE h.id IS NULL;

-- 4.2 Туры со ссылками на несуществующих операторов
SELECT t.id, t.operator_id
FROM tours t
LEFT JOIN tour_operators op ON t.operator_id = op.id
WHERE op.id IS NULL;

-- 4.3 Бронирования со ссылками на несуществующих пользователей
SELECT b.id, b.user_id
FROM bookings b
LEFT JOIN users u ON b.user_id = u.id
WHERE u.id IS NULL;

-- 4.4 Бронирования со ссылками на несуществующие туры
SELECT b.id, b.tour_id
FROM bookings b
LEFT JOIN tours t ON b.tour_id = t.id
WHERE t.id IS NULL;

-- 4.5 Отели со ссылками на несуществующие курорты
SELECT h.id, h.resort_id
FROM hotels h
LEFT JOIN resorts r ON h.resort_id = r.id
WHERE r.id IS NULL;

-- ============================================================
-- РАЗДЕЛ 5: СТАТИСТИКА RAW-ДАННЫХ
-- ============================================================

-- 5.1 Обработанные vs необработанные сырые отели
SELECT is_processed, COUNT(*) AS cnt,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM hotels_raw), 1) AS pct
FROM hotels_raw
GROUP BY is_processed;

-- 5.2 Типы ошибок в сырых турах
SELECT error_type, COUNT(*) AS cnt
FROM tours_raw
WHERE is_processed = 0
GROUP BY error_type
ORDER BY cnt DESC;

-- 5.3 Доля маппинга операторов
SELECT op.short_name AS operator,
       COUNT(om.id) AS mapping_count,
       ROUND(AVG(om.confidence), 2) AS avg_confidence
FROM tour_operators op
LEFT JOIN operator_mapping om ON op.id = om.operator_id
GROUP BY op.short_name;

-- ============================================================
-- РАЗДЕЛ 6: ОШИБКИ ЗАГРУЗКИ
-- ============================================================

-- 6.1 Неразрешённые ошибки
SELECT source_table, error_type, COUNT(*) AS cnt,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM load_errors), 1) AS pct
FROM load_errors
WHERE is_resolved = 0
GROUP BY source_table, error_type
ORDER BY cnt DESC;

-- 6.2 Все ошибки по типам
SELECT error_type, COUNT(*) AS cnt
FROM load_errors
GROUP BY error_type
ORDER BY cnt DESC;

-- 6.3 Статистика импортов по источникам
SELECT source_type,
       COUNT(*) AS runs,
       SUM(records_total) AS records_total,
       SUM(records_loaded) AS records_loaded,
       SUM(records_failed) AS records_failed
FROM source_import_runs
GROUP BY source_type
ORDER BY runs DESC;

-- ============================================================
-- РАЗДЕЛ 7: ОПТИМИЗАЦИЯ ЗАПРОСОВ
-- ============================================================

-- 7.1 EXPLAIN QUERY PLAN для частого запроса
EXPLAIN QUERY PLAN
SELECT * FROM tours WHERE country_id = 1 AND departure_date >= '2026-01-01' ORDER BY actual_price;

-- 7.2 EXPLAIN QUERY PLAN для аналитики
EXPLAIN QUERY PLAN
SELECT country_id, AVG(actual_price) FROM tours GROUP BY country_id;

-- 7.3 EXPLAIN QUERY PLAN для поиска
EXPLAIN QUERY PLAN
SELECT * FROM search_logs WHERE session_id = 'sess_1';

-- 7.4 Проверка использования индексов
SELECT name, tbl_name, sql FROM sqlite_master
WHERE type = 'index' AND sql IS NOT NULL
ORDER BY tbl_name, name;

-- ============================================================
-- РАЗДЕЛ 8: РЕКОМЕНДАЦИИ ПО НОВЫМ ПОЛЯМ / ТАБЛИЦАМ
-- ============================================================

-- Рекомендации (не SQL, а комментарии):
-- 1. Добавить поле avg_rating в hotels (средний рейтинг пользователей)
-- 2. Добавить поле review_count в hotels (количество отзывов)
-- 3. Создать таблицу hotel_amenities (удобства отеля: бассейн, WiFi, парковка)
-- 4. Создать таблицу tour_tags (теги тура: семейный, романтический, активный)
-- 5. Добавить поле search_rank в tours (позиция в выдаче)
-- 6. Создать таблицу price_alerts (подписки на снижение цены)
-- 7. Добавить поле cancellation_policy в tours
-- 8. Создать таблицу airports (аэропорты вылета)
-- 9. Добавить таблицу departure_cities (города вылета с привязкой к аэропортам)
-- 10. Создать таблицу competitor_prices (цены конкурентов для сравнения)
