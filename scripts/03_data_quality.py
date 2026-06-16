#!/usr/bin/env python3
"""Проверка качества данных."""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'download', 'tour_aggregator.db')


def format_status(result):
    """Вернуть человекочитаемый статус проверки."""
    return "ok" if result["failed"] == 0 else "есть замечания"


def run_check(cur, check_name, category, table, query, description=""):
    """Выполнить одну проверку качества и записать результат."""
    cur.execute(query)
    row = cur.fetchone()
    if row is None:
        return
    total = row[0]
    failed = row[1] if len(row) > 1 else 0
    fail_pct = round(failed * 100.0 / total, 2) if total > 0 else 0

    cur.execute("""
        INSERT INTO data_quality_reports (check_name, check_category, table_name, total_records, failed_records, fail_pct, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (check_name, category, table, total, failed, fail_pct, description))
    return {"check": check_name, "total": total, "failed": failed, "fail_pct": fail_pct}


def check_required_fields(cur):
    """Проверка обязательных полей."""
    checks = []

    # Туры без цены
    c = run_check(cur, "Туры без цены", "required_fields", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN actual_price IS NULL OR actual_price = 0 THEN 1 ELSE 0 END) FROM tours",
        "actual_price не должна быть NULL или 0")
    checks.append(c)

    # Туры без даты вылета
    c = run_check(cur, "Туры без даты вылета", "required_fields", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN departure_date IS NULL OR departure_date = '' THEN 1 ELSE 0 END) FROM tours",
        "departure_date обязательна")
    checks.append(c)

    # Туры без оператора
    c = run_check(cur, "Туры без оператора", "required_fields", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN operator_id IS NULL THEN 1 ELSE 0 END) FROM tours",
        "operator_id обязателен")
    checks.append(c)

    # Туры без отеля
    c = run_check(cur, "Туры без отеля", "required_fields", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN hotel_id IS NULL THEN 1 ELSE 0 END) FROM tours",
        "hotel_id обязателен")
    checks.append(c)

    # Отели без названия
    c = run_check(cur, "Отели без названия", "required_fields", "hotels",
        "SELECT COUNT(*), SUM(CASE WHEN name IS NULL OR name = '' THEN 1 ELSE 0 END) FROM hotels",
        "name обязателен")
    checks.append(c)

    # Отели без курорта
    c = run_check(cur, "Отели без курорта", "required_fields", "hotels",
        "SELECT COUNT(*), SUM(CASE WHEN resort_id IS NULL THEN 1 ELSE 0 END) FROM hotels",
        "resort_id обязателен")
    checks.append(c)

    # Бронирования без пользователя
    c = run_check(cur, "Бронирования без пользователя", "required_fields", "bookings",
        "SELECT COUNT(*), SUM(CASE WHEN user_id IS NULL THEN 1 ELSE 0 END) FROM bookings",
        "user_id обязателен")
    checks.append(c)

    return checks


def check_logical_integrity(cur):
    """Проверка логической целостности."""
    checks = []

    # Отрицательные цены
    c = run_check(cur, "Отрицательные цены туров", "integrity", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN actual_price < 0 THEN 1 ELSE 0 END) FROM tours",
        "Цена не может быть отрицательной")
    checks.append(c)

    # Нулевая длительность
    c = run_check(cur, "Нулевая/отрицательная длительность", "integrity", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN duration_nights <= 0 THEN 1 ELSE 0 END) FROM tours",
        "duration_nights > 0")
    checks.append(c)

    # Звёздность вне диапазона
    c = run_check(cur, "Звёздность вне [2,5]", "integrity", "hotels",
        "SELECT COUNT(*), SUM(CASE WHEN star_rating < 2 OR star_rating > 5 THEN 1 ELSE 0 END) FROM hotels",
        "star_rating в диапазоне [2, 5]")
    checks.append(c)

    # Нереалистичное число гостей
    c = run_check(cur, "Нереалистичное число гостей", "integrity", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN adults < 1 OR adults > 6 OR children < 0 OR children > 4 THEN 1 ELSE 0 END) FROM tours",
        "adults в [1,6], children в [0,4]")
    checks.append(c)

    # Бронирования с нулевой/отрицательной ценой
    c = run_check(cur, "Бронирования с ценой <= 0", "integrity", "bookings",
        "SELECT COUNT(*), SUM(CASE WHEN total_price <= 0 THEN 1 ELSE 0 END) FROM bookings",
        "total_price > 0")
    checks.append(c)

    # Некорректные статусы бронирований
    c = run_check(cur, "Некорректные статусы бронирований", "integrity", "bookings",
        """SELECT COUNT(*), SUM(CASE WHEN status NOT IN ('pending','confirmed','cancelled','completed') THEN 1 ELSE 0 END)
           FROM bookings""",
        "status в {pending, confirmed, cancelled, completed}")
    checks.append(c)

    # Цена за ночь > 100000 (аномалия)
    c = run_check(cur, "Аномально высокая цена за ночь", "integrity", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN actual_price / duration_nights > 100000 THEN 1 ELSE 0 END) FROM tours WHERE duration_nights > 0",
        "Цена за ночь не должна превышать 100000")
    checks.append(c)

    # Цена за ночь < 2000 (аномалия)
    c = run_check(cur, "Аномально низкая цена за ночь", "integrity", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN actual_price / duration_nights < 2000 THEN 1 ELSE 0 END) FROM tours WHERE duration_nights > 0",
        "Цена за ночь не должна быть ниже 2000")
    checks.append(c)

    return checks


def check_timeliness(cur):
    """Проверка актуальности данных."""
    checks = []

    # Устаревшие туры
    c = run_check(cur, "Устаревшие туры (дата прошла)", "timeliness", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN departure_date < date('now') AND is_available = 1 THEN 1 ELSE 0 END) FROM tours",
        "Недоступные туры с прошедшей датой")
    checks.append(c)

    # Доля актуальных туров
    c = run_check(cur, "Доля актуальных туров", "timeliness", "tours",
        "SELECT COUNT(*), SUM(CASE WHEN departure_date < date('now') THEN 1 ELSE 0 END) FROM tours",
        "Туры с прошедшей датой вылета")
    checks.append(c)

    # Последнее обновление по операторам
    cur.execute("""
        SELECT op.short_name, MAX(t.updated_at),
               ROUND((julianday('now') - julianday(MAX(t.updated_at))), 1)
        FROM tours t
        JOIN tour_operators op ON t.operator_id = op.id
        GROUP BY op.short_name
    """)
    for row in cur.fetchall():
        op_name, last_upd, days = row
        c = run_check(cur, f"Давность обновления: {op_name}", "timeliness", "tours",
            f"SELECT 1, CASE WHEN {int(days or 0)} > 7 THEN 1 ELSE 0 END",
            f"Последнее обновление: {last_upd}, дней назад: {days}")
        checks.append(c)

    return checks


def check_fk_integrity(cur):
    """Проверка целостности внешних ключей."""
    checks = []

    # Туры → Отели
    c = run_check(cur, "FK: tours.hotel_id → hotels.id", "fk_integrity", "tours",
        """SELECT COUNT(*), (SELECT COUNT(*) FROM tours t LEFT JOIN hotels h ON t.hotel_id = h.id WHERE h.id IS NULL) FROM tours""")
    checks.append(c)

    # Туры → Операторы
    c = run_check(cur, "FK: tours.operator_id → tour_operators.id", "fk_integrity", "tours",
        """SELECT COUNT(*), (SELECT COUNT(*) FROM tours t LEFT JOIN tour_operators op ON t.operator_id = op.id WHERE op.id IS NULL) FROM tours""")
    checks.append(c)

    # Бронирования → Пользователи
    c = run_check(cur, "FK: bookings.user_id → users.id", "fk_integrity", "bookings",
        """SELECT COUNT(*), (SELECT COUNT(*) FROM bookings b LEFT JOIN users u ON b.user_id = u.id WHERE u.id IS NULL) FROM bookings""")
    checks.append(c)

    # Бронирования → Туры
    c = run_check(cur, "FK: bookings.tour_id → tours.id", "fk_integrity", "bookings",
        """SELECT COUNT(*), (SELECT COUNT(*) FROM bookings b LEFT JOIN tours t ON b.tour_id = t.id WHERE t.id IS NULL) FROM bookings""")
    checks.append(c)

    # Отели → Курорты
    c = run_check(cur, "FK: hotels.resort_id → resorts.id", "fk_integrity", "hotels",
        """SELECT COUNT(*), (SELECT COUNT(*) FROM hotels h LEFT JOIN resorts r ON h.resort_id = r.id WHERE r.id IS NULL) FROM hotels""")
    checks.append(c)

    return checks


def check_raw_data(cur):
    """Проверка состояния сырых данных."""
    checks = []

    # Необработанные отели
    c = run_check(cur, "Необработанные сырые отели", "raw_data", "hotels_raw",
        "SELECT COUNT(*), SUM(CASE WHEN is_processed = 0 THEN 1 ELSE 0 END) FROM hotels_raw")
    checks.append(c)

    # Необработанные туры (ожидающие обработки, без ошибок)
    c = run_check(cur, "Необработанные сырые туры (без ошибок)", "raw_data", "tours_raw",
        "SELECT COUNT(*), SUM(CASE WHEN is_processed = 0 AND error_type IS NULL THEN 1 ELSE 0 END) FROM tours_raw")
    checks.append(c)

    # Типы ошибок
    cur.execute("SELECT error_type, COUNT(*) FROM tours_raw WHERE error_type IS NOT NULL GROUP BY error_type")
    for row in cur.fetchall():
        etype, cnt = row
        c = run_check(cur, f"Ошибка raw-туров: {etype}", "raw_data", "tours_raw",
            f"SELECT (SELECT COUNT(*) FROM tours_raw), {cnt}")
        checks.append(c)

    # Ошибки загрузки (только tours_raw, чтобы не дублировать счёт с проверкой выше)
    c = run_check(cur, "Ошибки загрузки сырых туров (load_errors)", "raw_data", "load_errors",
        "SELECT COUNT(*), SUM(CASE WHEN is_resolved = 0 AND source_table = 'tours_raw' THEN 1 ELSE 0 END) FROM load_errors",
        "Ошибки импорта туров; пересекаются с tours_raw — не суммировать отдельно с проверкой выше")
    checks.append(c)

    # Дубликаты отелей на разборе
    c = run_check(cur, "Дубликаты отелей (pending)", "raw_data", "hotel_duplicates",
        "SELECT COUNT(*), SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) FROM hotel_duplicates")
    checks.append(c)

    # Импорты с ошибками
    c = run_check(cur, "Импорты источников с ошибками", "raw_data", "source_import_runs",
        "SELECT COUNT(*), SUM(CASE WHEN records_failed > 0 THEN 1 ELSE 0 END) FROM source_import_runs")
    checks.append(c)

    return checks


def check_duplicates(cur):
    """Статистика дубликатов."""
    checks = []

    # Дубли отелей по статусам
    cur.execute("SELECT status, COUNT(*) FROM hotel_duplicates GROUP BY status")
    for row in cur.fetchall():
        status, cnt = row
        c = run_check(cur, f"Дубликаты отелей: {status}", "duplicates", "hotel_duplicates",
            f"SELECT {cnt}, {cnt if status == 'pending' else 0}")
        checks.append(c)

    # Дубли туры (одинаковые operator+hotel+date+meal+adults+children, только доступные)
    c = run_check(cur, "Дубли туров (operator+отель+дата+питание+ад/дет)", "duplicates", "tours",
        """SELECT COUNT(*), (SELECT COUNT(*) FROM (
            SELECT operator_id, hotel_id, departure_date, meal_type, adults, children, COUNT(*) as cnt
            FROM tours WHERE is_available = 1
            GROUP BY operator_id, hotel_id, departure_date, meal_type, adults, children HAVING cnt > 1
        )) FROM tours WHERE is_available = 1""")
    checks.append(c)

    return checks


def run_all_checks():
    """Запуск всех проверок качества данных."""
    if not os.path.exists(DB_PATH):
        print("[ERROR] База данных не найдена. Сначала запустите 01_generate_data.py")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Очищаем предыдущие отчёты
    cur.execute("DELETE FROM data_quality_reports")
    conn.commit()

    print("=== ПРОВЕРКА КАЧЕСТВА ДАННЫХ ===\n")

    print("[1/6] Проверка обязательных полей...")
    results = check_required_fields(cur)
    for r in results:
        if r:
            status = format_status(r)
            print(f"  {status} {r['check']}: {r['failed']}/{r['total']} ошибок ({r['fail_pct']}%)")

    print("\n[2/6] Проверка логической целостности...")
    results = check_logical_integrity(cur)
    for r in results:
        if r:
            status = format_status(r)
            print(f"  {status} {r['check']}: {r['failed']}/{r['total']} ошибок ({r['fail_pct']}%)")

    print("\n[3/6] Проверка актуальности...")
    results = check_timeliness(cur)
    for r in results:
        if r:
            status = format_status(r)
            print(f"  {status} {r['check']}: {r['failed']}/{r['total']} ошибок ({r['fail_pct']}%)")

    print("\n[4/6] Проверка FK-целостности...")
    results = check_fk_integrity(cur)
    for r in results:
        if r:
            status = format_status(r)
            print(f"  {status} {r['check']}: {r['failed']}/{r['total']} ошибок ({r['fail_pct']}%)")

    print("\n[5/6] Проверка raw-данных...")
    results = check_raw_data(cur)
    for r in results:
        if r:
            status = format_status(r)
            print(f"  {status} {r['check']}: {r['failed']}/{r['total']} ошибок ({r['fail_pct']}%)")

    print("\n[6/6] Проверка дубликатов...")
    results = check_duplicates(cur)
    for r in results:
        if r:
            status = format_status(r)
            print(f"  {status} {r['check']}: {r['failed']}/{r['total']} ошибок ({r['fail_pct']}%)")

    conn.commit()

    # Итоговый отчёт
    cur.execute("SELECT COUNT(*), SUM(failed_records), AVG(fail_pct) FROM data_quality_reports")
    total_checks, total_failed, avg_fail = cur.fetchone()
    print(f"\n=== ИТОГ ===")
    print(f"  Всего проверок: {total_checks}")
    print(f"  Проверок с ошибками: {total_failed}")
    print(f"  Средний % ошибок: {round(avg_fail or 0, 2)}%")

    # Категории с проблемами
    cur.execute("""
        SELECT check_category, COUNT(*) AS cnt, SUM(failed_records) AS fails
        FROM data_quality_reports
        WHERE failed_records > 0
        GROUP BY check_category
        ORDER BY fails DESC
    """)
    problem_cats = cur.fetchall()
    if problem_cats:
        print(f"\n  Категории с проблемами:")
        for cat, cnt, fails in problem_cats:
            print(f"    - {cat}: {fails} ошибок в {cnt} проверках")

    conn.close()
    print("\n[READY] Проверка качества завершена. Результаты в data_quality_reports")


if __name__ == "__main__":
    run_all_checks()
