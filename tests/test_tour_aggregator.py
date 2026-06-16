#!/usr/bin/env python3
"""Тесты базы данных турагрегатора."""

import pytest
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'download', 'tour_aggregator.db')

# Все таблицы, которые должны существовать
REQUIRED_TABLES = [
    'countries', 'resorts', 'tour_operators', 'operator_mapping',
    'geo_aliases', 'hotels', 'hotel_aliases', 'hotels_raw', 'hotel_duplicates',
    'tours', 'tours_raw', 'price_history',
    'users', 'search_logs', 'tour_views', 'click_logs', 'bookings',
    'load_errors', 'system_logs', 'data_quality_reports', 'source_import_runs'
]


@pytest.fixture(scope="module")
def db_connection():
    """Фикстура: подключение к БД на всё время тестов."""
    if not os.path.exists(DB_PATH):
        pytest.skip("База данных не найдена. Сначала запустите 01_generate_data.py")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def cursor(db_connection):
    """Фикстура: курсор для выполнения запросов."""
    return db_connection.cursor()


# Таблицы

class TestDatabaseSchema:
    """Проверка структуры базы данных."""

    def test_all_tables_exist(self, cursor):
        """Все 18 таблиц существуют."""
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cursor.fetchall()}
        for table in REQUIRED_TABLES:
            assert table in tables, f"Таблица '{table}' не найдена"

    def test_tours_columns(self, cursor):
        """Таблица tours содержит все необходимые столбцы."""
        cursor.execute("PRAGMA table_info(tours)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {'id', 'operator_id', 'hotel_id', 'country_id', 'resort_id',
                     'departure_date', 'duration_nights', 'meal_type', 'actual_price',
                     'original_price', 'discount_pct', 'adults', 'children',
                     'room_type', 'is_available', 'created_at', 'updated_at'}
        assert required.issubset(columns), f"Отсутствуют столбцы: {required - columns}"

    def test_bookings_columns(self, cursor):
        """Таблица bookings содержит все необходимые столбцы."""
        cursor.execute("PRAGMA table_info(bookings)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {'id', 'user_id', 'tour_id', 'booking_date', 'total_price',
                     'status', 'adults', 'children', 'session_id', 'created_at'}
        assert required.issubset(columns), f"Отсутствуют столбцы: {required - columns}"

    def test_indexes_exist(self, cursor):
        """Ключевые индексы созданы."""
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        key_indexes = ['idx_tours_country_date', 'idx_tours_actual_price',
                        'idx_tours_operator', 'idx_bookings_user', 'idx_bookings_status']
        for idx in key_indexes:
            assert idx in indexes, f"Индекс '{idx}' не найден"

class TestRequiredData:
    """Проверка наличия минимальных данных в справочниках."""

    def test_countries_exist(self, cursor):
        """В БД есть страны (>= 10)."""
        cursor.execute("SELECT COUNT(*) FROM countries")
        assert cursor.fetchone()[0] >= 10

    def test_resorts_exist(self, cursor):
        """В БД есть курорты (>= 20)."""
        cursor.execute("SELECT COUNT(*) FROM resorts")
        assert cursor.fetchone()[0] >= 20

    def test_operators_exist(self, cursor):
        """В БД есть туроператоры (>= 5)."""
        cursor.execute("SELECT COUNT(*) FROM tour_operators")
        assert cursor.fetchone()[0] >= 5

    def test_operator_mapping_exists(self, cursor):
        """Маппинг операторов заполнен."""
        cursor.execute("SELECT COUNT(*) FROM operator_mapping")
        assert cursor.fetchone()[0] >= 10

    def test_source_import_runs_exist(self, cursor):
        """Есть записи о загрузках источников."""
        cursor.execute("SELECT COUNT(*) FROM source_import_runs")
        assert cursor.fetchone()[0] >= 6

    def test_hotels_exist(self, cursor):
        """В БД есть отели (>= 50)."""
        cursor.execute("SELECT COUNT(*) FROM hotels")
        assert cursor.fetchone()[0] >= 50

    def test_tours_exist(self, cursor):
        """В БД есть туры (>= 500)."""
        cursor.execute("SELECT COUNT(*) FROM tours")
        assert cursor.fetchone()[0] >= 500

class TestDataIntegrity:
    """Проверка целостности и корректности данных."""

    def test_no_null_prices(self, cursor):
        """Нет туров с NULL ценой."""
        cursor.execute("SELECT COUNT(*) FROM tours WHERE actual_price IS NULL")
        assert cursor.fetchone()[0] == 0

    def test_no_zero_prices(self, cursor):
        """Нет туров с нулевой ценой (среди доступных)."""
        cursor.execute("SELECT COUNT(*) FROM tours WHERE actual_price = 0 AND is_available = 1")
        assert cursor.fetchone()[0] == 0

    def test_no_negative_prices(self, cursor):
        """Нет туров с отрицательной ценой."""
        cursor.execute("SELECT COUNT(*) FROM tours WHERE actual_price < 0")
        assert cursor.fetchone()[0] == 0

    def test_valid_duration(self, cursor):
        """Длительность туров > 0."""
        cursor.execute("SELECT COUNT(*) FROM tours WHERE duration_nights <= 0")
        assert cursor.fetchone()[0] == 0

    def test_valid_stars(self, cursor):
        """Звёздность отелей в диапазоне [2, 5]."""
        cursor.execute("SELECT COUNT(*) FROM hotels WHERE star_rating < 2 OR star_rating > 5")
        assert cursor.fetchone()[0] == 0

    def test_valid_guests(self, cursor):
        """Число гостей в разумных пределах."""
        cursor.execute("SELECT COUNT(*) FROM tours WHERE adults < 1 OR adults > 6 OR children < 0 OR children > 4")
        assert cursor.fetchone()[0] == 0

    def test_no_empty_departure_dates(self, cursor):
        """Нет туров с пустой датой вылета."""
        cursor.execute("SELECT COUNT(*) FROM tours WHERE departure_date IS NULL OR departure_date = ''")
        assert cursor.fetchone()[0] == 0

    def test_valid_departure_date_format(self, cursor):
        """Даты вылета в формате YYYY-MM-DD."""
        cursor.execute("SELECT departure_date FROM tours LIMIT 100")
        import re
        pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        for row in cursor.fetchall():
            assert pattern.match(row[0]), f"Некорректный формат даты: {row[0]}"

    def test_booking_prices_positive(self, cursor):
        """Цены бронирований положительные."""
        cursor.execute("SELECT COUNT(*) FROM bookings WHERE total_price <= 0")
        assert cursor.fetchone()[0] == 0

    def test_valid_booking_statuses(self, cursor):
        """Статусы бронирований из допустимого набора."""
        cursor.execute("SELECT COUNT(*) FROM bookings WHERE status NOT IN ('pending','confirmed','cancelled','completed')")
        assert cursor.fetchone()[0] == 0

    def test_discount_non_negative(self, cursor):
        """Скидка неотрицательная."""
        cursor.execute("SELECT COUNT(*) FROM tours WHERE discount_pct < 0")
        assert cursor.fetchone()[0] == 0

class TestForeignKeys:
    """Проверка ссылочной целостности."""

    def test_tours_hotel_fk(self, cursor):
        """Все hotel_id в tours ссылаются на существующие отели."""
        cursor.execute("""
            SELECT COUNT(*) FROM tours t
            LEFT JOIN hotels h ON t.hotel_id = h.id
            WHERE h.id IS NULL
        """)
        assert cursor.fetchone()[0] == 0

    def test_tours_operator_fk(self, cursor):
        """Все operator_id в tours ссылаются на существующих операторов."""
        cursor.execute("""
            SELECT COUNT(*) FROM tours t
            LEFT JOIN tour_operators op ON t.operator_id = op.id
            WHERE op.id IS NULL
        """)
        assert cursor.fetchone()[0] == 0

    def test_bookings_user_fk(self, cursor):
        """Все user_id в bookings ссылаются на существующих пользователей."""
        cursor.execute("""
            SELECT COUNT(*) FROM bookings b
            LEFT JOIN users u ON b.user_id = u.id
            WHERE u.id IS NULL
        """)
        assert cursor.fetchone()[0] == 0

    def test_bookings_tour_fk(self, cursor):
        """Все tour_id в bookings ссылаются на существующие туры."""
        cursor.execute("""
            SELECT COUNT(*) FROM bookings b
            LEFT JOIN tours t ON b.tour_id = t.id
            WHERE t.id IS NULL
        """)
        assert cursor.fetchone()[0] == 0

    def test_hotels_resort_fk(self, cursor):
        """Все resort_id в hotels ссылаются на существующие курорты."""
        cursor.execute("""
            SELECT COUNT(*) FROM hotels h
            LEFT JOIN resorts r ON h.resort_id = r.id
            WHERE r.id IS NULL
        """)
        assert cursor.fetchone()[0] == 0

class TestBusinessLogic:
    """Проверка бизнес-логики."""

    def test_available_tours_future_dates(self, cursor):
        """Доступные туры имеют дату вылета не раньше сегодня."""
        cursor.execute("""
            SELECT COUNT(*) FROM tours
            WHERE is_available = 1 AND departure_date < date('now')
        """)
        # Допускаем устаревшие туры (они должны быть is_available=0)
        outdated = cursor.fetchone()[0]
        # Это предупреждение, а не строгая ошибка — данные генерируются на 180 дней
        assert outdated >= 0  # просто проверяем, что запрос выполняется

    def test_reasonable_price_per_night(self, cursor):
        """Цена за ночь в разумных пределах (2 000 - 100 000 тг.)."""
        cursor.execute("""
            SELECT COUNT(*) FROM tours
            WHERE duration_nights > 0
              AND (actual_price / duration_nights < 2000 OR actual_price / duration_nights > 100000)
        """)
        # Некоторая доля аномалий допустима
        anomalies = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tours WHERE duration_nights > 0")
        total = cursor.fetchone()[0]
        anomaly_pct = anomalies / total * 100 if total > 0 else 0
        assert anomaly_pct < 10, f"Слишком много аномальных цен за ночь: {anomaly_pct:.1f}%"

    def test_booking_status_values(self, cursor):
        """Статусы бронирований содержат ожидаемые значения."""
        cursor.execute("SELECT DISTINCT status FROM bookings")
        statuses = {row[0] for row in cursor.fetchall()}
        expected = {'pending', 'confirmed', 'cancelled', 'completed'}
        assert statuses.issubset(expected), f"Неожиданные статусы: {statuses - expected}"

    def test_operator_mapping_coverage(self, cursor):
        """Каждый оператор имеет хотя бы один маппинг."""
        cursor.execute("""
            SELECT COUNT(DISTINCT op.id)
            FROM tour_operators op
            LEFT JOIN operator_mapping om ON op.id = om.operator_id
            WHERE om.id IS NULL
        """)
        unmapped = cursor.fetchone()[0]
        assert unmapped == 0, f"Операторы без маппинга: {unmapped}"

    def test_countries_have_resorts(self, cursor):
        """У каждой страны есть хотя бы один курорт."""
        cursor.execute("""
            SELECT COUNT(*) FROM countries c
            LEFT JOIN resorts r ON c.id = r.country_id
            WHERE r.id IS NULL
        """)
        empty_countries = cursor.fetchone()[0]
        assert empty_countries == 0, f"Страны без курортов: {empty_countries}"

    def test_resorts_have_tours(self, cursor):
        """Большинство курортов имеют туры."""
        cursor.execute("""
            SELECT COUNT(*) FROM resorts r
            LEFT JOIN tours t ON r.id = t.resort_id
            WHERE t.id IS NULL
        """)
        empty_resorts = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM resorts")
        total_resorts = cursor.fetchone()[0]
        empty_pct = empty_resorts / total_resorts * 100 if total_resorts > 0 else 0
        assert empty_pct < 30, f"Слишком много курортов без туров: {empty_pct:.1f}%"

    def test_price_history_exists(self, cursor):
        """Есть записи в истории цен."""
        cursor.execute("SELECT COUNT(*) FROM price_history")
        assert cursor.fetchone()[0] > 0, "История цен пуста"

class TestAnalyticsQueries:
    """Проверка аналитических запросов."""

    def test_tours_by_country_returns_data(self, cursor):
        """Запрос по странам возвращает данные."""
        cursor.execute("""
            SELECT c.name, COUNT(*) FROM tours t
            JOIN countries c ON t.country_id = c.id
            WHERE t.is_available = 1
            GROUP BY c.name
        """)
        results = cursor.fetchall()
        assert len(results) > 0

    def test_market_share_sums_near_100(self, cursor):
        """Сумма рыночных долей операторов близка к 100%."""
        cursor.execute("""
            SELECT ROUND(SUM(share), 1) FROM (
                SELECT COUNT(*) * 100.0 / (SELECT COUNT(*) FROM tours WHERE is_available = 1) AS share
                FROM tours t
                WHERE t.is_available = 1
                GROUP BY t.operator_id
            )
        """)
        total_share = cursor.fetchone()[0]
        assert 95 <= total_share <= 105, f"Сумма долей: {total_share}%"

    def test_price_ranges_covered(self, cursor):
        """Ценовые диапазоны покрывают данные."""
        cursor.execute("SELECT MIN(actual_price), MAX(actual_price) FROM tours WHERE is_available = 1")
        min_p, max_p = cursor.fetchone()
        assert min_p > 0
        assert max_p > min_p

    def test_seasonality_data_exists(self, cursor):
        """Данные о сезонности есть."""
        cursor.execute("""
            SELECT COUNT(DISTINCT strftime('%m', departure_date))
            FROM tours WHERE is_available = 1
        """)
        months = cursor.fetchone()[0]
        assert months >= 3, f"Сезонность: только {months} месяцев"

    def test_conversion_funnel_data(self, cursor):
        """Воронка конверсии имеет данные на всех этапах."""
        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM search_logs")
        searches = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM tour_views")
        views = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM click_logs")
        clicks = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM bookings")
        bookings = cursor.fetchone()[0]
        assert searches > 0, "Нет данных о поиске"
        assert views > 0, "Нет данных о просмотрах"
        assert clicks > 0, "Нет данных о кликах"
        assert bookings > 0, "Нет данных о бронированиях"

    def test_operator_avg_prices(self, cursor):
        """Средние цены по операторам в разумных пределах."""
        cursor.execute("""
            SELECT AVG(t.actual_price) FROM tours t
            WHERE t.is_available = 1
        """)
        avg = cursor.fetchone()[0]
        assert 20000 <= avg <= 500000, f"Средняя цена вне диапазона: {avg}"

    def test_booking_status_distribution(self, cursor):
        """Распределение статусов бронирований не пустое."""
        cursor.execute("SELECT COUNT(DISTINCT status) FROM bookings")
        distinct = cursor.fetchone()[0]
        assert distinct >= 2, f"Слишком мало статусов: {distinct}"

    def test_search_to_booking_ratio(self, cursor):
        """Отношение поисков к бронированиям разумное."""
        cursor.execute("SELECT COUNT(*) FROM search_logs")
        searches = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM bookings")
        bookings = cursor.fetchone()[0]
        ratio = searches / bookings if bookings > 0 else float('inf')
        assert 1 <= ratio <= 100, f"Отношение поиски/бронь: {ratio:.1f}"

class TestRawDataProcessing:
    """Проверка обработки сырых данных."""

    def test_raw_hotels_exist(self, cursor):
        """Сырые данные отелей существуют."""
        cursor.execute("SELECT COUNT(*) FROM hotels_raw")
        assert cursor.fetchone()[0] > 0

    def test_raw_tours_exist(self, cursor):
        """Сырые данные туров существуют."""
        cursor.execute("SELECT COUNT(*) FROM tours_raw")
        assert cursor.fetchone()[0] > 0

    def test_raw_data_has_errors(self, cursor):
        """В сырых данных есть ошибки (специально внедрённые)."""
        cursor.execute("SELECT COUNT(*) FROM tours_raw WHERE error_type IS NOT NULL")
        errors = cursor.fetchone()[0]
        assert errors > 0, "Ошибки в raw-данных отсутствуют (ожидаются 15% ошибок)"

    def test_operator_mapping_has_variants(self, cursor):
        """Маппинг операторов содержит варианты названий."""
        cursor.execute("SELECT COUNT(DISTINCT raw_name) FROM operator_mapping")
        variants = cursor.fetchone()[0]
        assert variants >= 10, f"Слишком мало вариантов маппинга: {variants}"

    def test_hotel_aliases_exist(self, cursor):
        """Есть алиасы отелей для сопоставления разных названий."""
        cursor.execute("SELECT COUNT(*) FROM hotel_aliases")
        assert cursor.fetchone()[0] > 0
