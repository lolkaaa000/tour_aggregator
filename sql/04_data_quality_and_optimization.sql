-- Качество данных

-- Актуальность данных

-- Устаревшие туры
SELECT COUNT(*) AS outdated_tours
FROM tours
WHERE departure_date < date('now') AND is_available = 1;

-- Доля актуальных туров
SELECT
    COUNT(*) AS total_tours,
    SUM(CASE WHEN departure_date >= date('now') THEN 1 ELSE 0 END) AS current_tours,
    ROUND(SUM(CASE WHEN departure_date >= date('now') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS current_pct
FROM tours;

-- Последнее обновление по операторам
SELECT op.short_name AS operator,
       COUNT(*) AS tour_count,
       MAX(t.updated_at) AS last_updated,
       ROUND((julianday('now') - julianday(MAX(t.updated_at))), 1) AS days_since_update
FROM tours t
JOIN tour_operators op ON t.operator_id = op.id
GROUP BY op.short_name
ORDER BY days_since_update DESC;

-- Обязательные поля

-- Туры без цены
SELECT COUNT(*) AS tours_no_price FROM tours WHERE actual_price IS NULL OR actual_price = 0;

-- Туры без даты вылета
SELECT COUNT(*) AS tours_no_date FROM tours WHERE departure_date IS NULL OR departure_date = '';

-- Отели без курорта
SELECT COUNT(*) AS hotels_no_resort FROM hotels WHERE resort_id IS NULL;

-- Туры без оператора
SELECT COUNT(*) AS tours_no_operator FROM tours WHERE operator_id IS NULL;

-- Сырые записи без маппинга
SELECT 'hotels_raw' AS tbl, COUNT(*) AS unprocessed FROM hotels_raw WHERE is_processed = 0
UNION ALL
SELECT 'tours_raw', COUNT(*) FROM tours_raw WHERE is_processed = 0;

-- Логическая целостность

-- Туры с отрицательной ценой
SELECT id, actual_price, hotel_id, operator_id
FROM tours WHERE actual_price < 0;

-- Туры с нулевой длительностью
SELECT id, duration_nights, actual_price
FROM tours WHERE duration_nights <= 0;

-- Отели со звёздностью вне диапазона [2, 5]
SELECT id, name, star_rating
FROM hotels WHERE star_rating < 2 OR star_rating > 5;

-- Туры с нереалистичным числом гостей
SELECT id, adults, children, actual_price
FROM tours WHERE adults < 1 OR adults > 6 OR children < 0 OR children > 4;

-- Бронирования с ценой 0 или отрицательной
SELECT id, user_id, total_price, status
FROM bookings WHERE total_price <= 0;

-- Даты заезда раньше даты бронирования
SELECT b.id, b.booking_date, t.departure_date
FROM bookings b
JOIN tours t ON b.tour_id = t.id
WHERE t.departure_date < b.booking_date;

-- Внешние ключи

-- Туры со ссылками на несуществующие отели
SELECT t.id, t.hotel_id
FROM tours t
LEFT JOIN hotels h ON t.hotel_id = h.id
WHERE h.id IS NULL;

-- Туры со ссылками на несуществующих операторов
SELECT t.id, t.operator_id
FROM tours t
LEFT JOIN tour_operators op ON t.operator_id = op.id
WHERE op.id IS NULL;

-- Бронирования со ссылками на несуществующих пользователей
SELECT b.id, b.user_id
FROM bookings b
LEFT JOIN users u ON b.user_id = u.id
WHERE u.id IS NULL;

-- Бронирования со ссылками на несуществующие туры
SELECT b.id, b.tour_id
FROM bookings b
LEFT JOIN tours t ON b.tour_id = t.id
WHERE t.id IS NULL;

-- Отели со ссылками на несуществующие курорты
SELECT h.id, h.resort_id
FROM hotels h
LEFT JOIN resorts r ON h.resort_id = r.id
WHERE r.id IS NULL;

-- Статистика сырых данных

-- Обработанные vs необработанные сырые отели
SELECT is_processed, COUNT(*) AS cnt,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM hotels_raw), 1) AS pct
FROM hotels_raw
GROUP BY is_processed;

-- Типы ошибок в сырых турах
SELECT error_type, COUNT(*) AS cnt
FROM tours_raw
WHERE is_processed = 0
GROUP BY error_type
ORDER BY cnt DESC;

-- Доля маппинга операторов
SELECT op.short_name AS operator,
       COUNT(om.id) AS mapping_count,
       ROUND(AVG(om.confidence), 2) AS avg_confidence
FROM tour_operators op
LEFT JOIN operator_mapping om ON op.id = om.operator_id
GROUP BY op.short_name;

-- Ошибки загрузки

-- Неразрешённые ошибки
SELECT source_table, error_type, COUNT(*) AS cnt,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM load_errors), 1) AS pct
FROM load_errors
WHERE is_resolved = 0
GROUP BY source_table, error_type
ORDER BY cnt DESC;

-- Все ошибки по типам
SELECT error_type, COUNT(*) AS cnt
FROM load_errors
GROUP BY error_type
ORDER BY cnt DESC;

-- Статистика импортов по источникам
SELECT source_type,
       COUNT(*) AS runs,
       SUM(records_total) AS records_total,
       SUM(records_loaded) AS records_loaded,
       SUM(records_failed) AS records_failed
FROM source_import_runs
GROUP BY source_type
ORDER BY runs DESC;

-- Оптимизация запросов

-- EXPLAIN частого запроса
EXPLAIN QUERY PLAN
SELECT * FROM tours WHERE country_id = 1 AND departure_date >= '2026-01-01' ORDER BY actual_price;

-- EXPLAIN аналитики
EXPLAIN QUERY PLAN
SELECT country_id, AVG(actual_price) FROM tours GROUP BY country_id;

-- EXPLAIN поиска
EXPLAIN QUERY PLAN
SELECT * FROM search_logs WHERE session_id = 'sess_1';

-- Индексы в базе
SELECT name, tbl_name, sql FROM sqlite_master
WHERE type = 'index' AND sql IS NOT NULL
ORDER BY tbl_name, name;
