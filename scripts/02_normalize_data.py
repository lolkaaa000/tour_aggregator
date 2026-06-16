#!/usr/bin/env python3
"""
Нормализация и дедупликация данных турагрегатора.
- Нормализация стран, курортов, питания и звёздности
- Маппинг отелей по алиасам и fuzzy matching
- Обработка сырых туров и создание/сопоставление нормализованных туров
- Дедупликация отелей и туров
"""

from __future__ import annotations

import os
import re
import sqlite3
from difflib import SequenceMatcher

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "download", "tour_aggregator.db")

COUNTRY_MAPPING = {
    "Турций": "Турция", "Турции": "Турция", "Türkiye": "Турция", "Turkey": "Турция",
    "Египт": "Египет", "Egypt": "Египет",
    "Таеланд": "Таиланд", "Тайланд": "Таиланд", "Thailand": "Таиланд",
    "ОАЕ": "ОАЭ", "UAE": "ОАЭ", "Объединенные Арабские Эмираты": "ОАЭ",
    "Vietnam": "Вьетнам", "Sri Lanka": "Шри-Ланка", "Cyprus": "Кипр", "Greece": "Греция",
    "Spain": "Испания", "Italy": "Италия", "Montenegro": "Черногория",
    "Dominican Republic": "Доминикана", "Доминиканская Республика": "Доминикана",
    "Mexico": "Мексика", "Maldives": "Мальдивы", "Tunisia": "Тунис",
    "Morocco": "Марокко", "Russia": "Россия", "Cuba": "Куба",
}

MEAL_MAPPING = {
    "AI": "AI", "all inclusive": "AI", "всё включено": "AI", "все включено": "AI", "All Inclusive": "AI", "All": "AI", "Всё!": "AI",
    "UAI": "UAI", "Ultra All Inclusive": "UAI", "ультра всё включено": "UAI",
    "FB": "FB", "FB+": "FB", "Full Board": "FB", "полный пансион": "FB",
    "HB": "HB", "Half Board": "HB", "полупансион": "HB", "питание": "HB",
    "BB": "BB", "Bed & Breakfast": "BB", "завтраки": "BB", "завтрак": "BB",
    "OB": "OB", "Room Only": "OB", "только кровать": "OB",
    "RO": "RO", "Without Meal": "RO", "без питания": "RO",
}


def normalize_text(value):
    if value is None:
        return None
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def normalize_country(name):
    name = normalize_text(name)
    if not name:
        return None
    return COUNTRY_MAPPING.get(name, name)


def normalize_meal(raw_meal):
    raw_meal = normalize_text(raw_meal)
    if not raw_meal:
        return None
    return MEAL_MAPPING.get(raw_meal, MEAL_MAPPING.get(raw_meal.lower(), raw_meal))


def parse_stars(raw_stars):
    raw_stars = normalize_text(raw_stars)
    if not raw_stars:
        return None
    try:
        value = float(raw_stars)
        return value if 1 <= value <= 5 else None
    except ValueError:
        return {"пять": 5, "четыре": 4, "три": 3, "два": 2, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}.get(raw_stars.lower())


def parse_positive_int(value, default=None):
    value = normalize_text(value)
    if value is None:
        return default
    if not re.fullmatch(r"-?\d+", value):
        return default
    return int(value)


def parse_price(raw_price):
    value = normalize_text(raw_price)
    if value is None:
        return None
    try:
        return float(value.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def normalize_resort(cur, name, country_id=None):
    name = normalize_text(name)
    if not name:
        return None
    cur.execute(
        """
        SELECT canonical_name FROM geo_aliases
        WHERE entity_type = 'resort' AND alias_name = ?
        ORDER BY confidence DESC
        LIMIT 1
        """,
        (name,),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute("SELECT name FROM resorts WHERE (? IS NULL OR country_id = ?)", (country_id, country_id))
    best_name = None
    best_score = 0
    for (candidate,) in cur.fetchall():
        score = SequenceMatcher(None, name.lower(), candidate.lower()).ratio()
        if score > best_score and score >= 0.8:
            best_score = score
            best_name = candidate
    return best_name or name


def find_hotel_match(cur, operator_id, raw_name, country_name, resort_name):
    raw_name = normalize_text(raw_name)
    if not raw_name or not country_name or not resort_name:
        return None

    cur.execute(
        """
        SELECT ha.hotel_id
        FROM hotel_aliases ha
        JOIN hotels h ON h.id = ha.hotel_id
        JOIN resorts r ON h.resort_id = r.id
        JOIN countries c ON r.country_id = c.id
        WHERE ha.alias_name = ? AND (ha.operator_id = ? OR ha.operator_id IS NULL)
          AND c.name = ? AND r.name = ?
        ORDER BY CASE WHEN ha.operator_id = ? THEN 0 ELSE 1 END, ha.confidence DESC
        LIMIT 1
        """,
        (raw_name, operator_id, country_name, resort_name, operator_id),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        SELECT h.id, h.name
        FROM hotels h
        JOIN resorts r ON h.resort_id = r.id
        JOIN countries c ON r.country_id = c.id
        WHERE c.name = ? AND r.name = ?
        """,
        (country_name, resort_name),
    )
    best_match = None
    best_score = 0
    for hotel_id, hotel_name in cur.fetchall():
        score = SequenceMatcher(None, raw_name.lower(), hotel_name.lower()).ratio()
        if score > best_score and score >= 0.82:
            best_match = hotel_id
            best_score = score
    return best_match


def ensure_hotel_alias(cur, hotel_id, operator_id, alias_name, source_name):
    alias_name = normalize_text(alias_name)
    if not alias_name or not hotel_id:
        return
    cur.execute(
        """
        INSERT OR IGNORE INTO hotel_aliases (hotel_id, operator_id, alias_name, source, confidence)
        VALUES (?, ?, ?, ?, 0.95)
        """,
        (hotel_id, operator_id, alias_name, source_name),
    )


def register_load_error(cur, source_table, raw_id, error_type, message, raw_payload):
    cur.execute(
        """
        INSERT INTO load_errors (source_table, raw_record_id, error_type, error_message, raw_data, is_resolved)
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (source_table, raw_id, error_type, message, raw_payload),
    )


def normalize_raw_hotels(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, operator_id, raw_name, raw_country, raw_resort, raw_stars, raw_meal, source_name
        FROM hotels_raw
        WHERE is_processed = 0
        """
    )
    rows = cur.fetchall()
    processed = 0
    matched = 0

    for raw_id, operator_id, raw_name, raw_country, raw_resort, raw_stars, raw_meal, source_name in rows:
        country_name = normalize_country(raw_country)
        country_id = None
        if country_name:
            cur.execute("SELECT id FROM countries WHERE name = ?", (country_name,))
            country = cur.fetchone()
            country_id = country[0] if country else None
        resort_name = normalize_resort(cur, raw_resort, country_id)
        hotel_id = find_hotel_match(cur, operator_id, raw_name, country_name, resort_name)
        if hotel_id:
            ensure_hotel_alias(cur, hotel_id, operator_id, raw_name, source_name)
            matched += 1
        cur.execute(
            "UPDATE hotels_raw SET hotel_id = ?, is_processed = 1, raw_stars = ?, raw_meal = ? WHERE id = ?",
            (hotel_id, parse_stars(raw_stars), normalize_meal(raw_meal), raw_id),
        )
        processed += 1

    conn.commit()
    print(f"  [OK] Обработано сырых отелей: {processed}")
    print(f"  [OK] Сопоставлено с нормализованными отелями: {matched}")


def find_existing_tour(cur, operator_id, hotel_id, departure_date, nights, meal_type, adults, children):
    cur.execute(
        """
        SELECT id
        FROM tours
        WHERE operator_id = ? AND hotel_id = ? AND departure_date = ?
          AND duration_nights = ? AND meal_type = ? AND adults = ? AND children = ?
        ORDER BY actual_price ASC
        LIMIT 1
        """,
        (operator_id, hotel_id, departure_date, nights, meal_type, adults, children),
    )
    row = cur.fetchone()
    return row[0] if row else None


def create_missing_tour(cur, operator_id, hotel_id, departure_date, nights, meal_type, actual_price, adults, children):
    cur.execute(
        """
        SELECT r.id, c.id, h.meal_plan
        FROM hotels h
        JOIN resorts r ON h.resort_id = r.id
        JOIN countries c ON r.country_id = c.id
        WHERE h.id = ?
        """,
        (hotel_id,),
    )
    resort_id, country_id, hotel_meal = cur.fetchone()
    cur.execute(
        """
        INSERT INTO tours (
            operator_id, hotel_id, country_id, resort_id, departure_date, duration_nights,
            meal_type, actual_price, original_price, discount_pct, adults, children,
            room_type, is_available, source_url, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 'Imported', 1, ?, datetime('now'))
        """,
        (
            operator_id,
            hotel_id,
            country_id,
            resort_id,
            departure_date,
            nights,
            meal_type or hotel_meal,
            actual_price,
            actual_price,
            adults,
            children,
            f"https://imported.local/tour/{hotel_id}",
        ),
    )
    return cur.lastrowid


def normalize_raw_tours(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, operator_id, raw_hotel_name, raw_country, raw_resort, raw_price,
               raw_departure, raw_duration, raw_meal, raw_adults, raw_children, source_name
        FROM tours_raw
        WHERE is_processed = 0
        """
    )
    rows = cur.fetchall()
    processed = 0
    failed = 0
    created = 0

    for row in rows:
        raw_id, operator_id, raw_hotel_name, raw_country, raw_resort, raw_price, raw_departure, raw_duration, raw_meal, raw_adults, raw_children, source_name = row
        country_name = normalize_country(raw_country)
        cur.execute("SELECT id FROM countries WHERE name = ?", (country_name,))
        country_row = cur.fetchone()
        country_id = country_row[0] if country_row else None
        resort_name = normalize_resort(cur, raw_resort, country_id)
        meal_type = normalize_meal(raw_meal)
        price = parse_price(raw_price)
        nights = parse_positive_int(raw_duration)
        adults = parse_positive_int(raw_adults, default=2)
        children = parse_positive_int(raw_children, default=0)
        departure = normalize_text(raw_departure)

        error_type = None
        if not normalize_text(raw_hotel_name):
            error_type = "missing_hotel"
        elif price is None:
            error_type = "invalid_price"
        elif price <= 0:
            error_type = "non_positive_price"
        elif not departure or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", departure):
            error_type = "bad_date"
        elif nights is None or nights <= 0:
            error_type = "bad_duration"
        elif adults is None or adults < 1 or adults > 6 or children is None or children < 0 or children > 4:
            error_type = "invalid_guests"

        hotel_id = None if error_type else find_hotel_match(cur, operator_id, raw_hotel_name, country_name, resort_name)
        if not error_type and not hotel_id:
            error_type = "hotel_not_matched"

        if error_type:
            cur.execute("UPDATE tours_raw SET error_type = ?, is_processed = 0 WHERE id = ?", (error_type, raw_id))
            register_load_error(
                cur,
                "tours_raw",
                raw_id,
                error_type,
                f"Ошибка обработки тура из {source_name}",
                str(
                    {
                        "hotel": raw_hotel_name,
                        "country": raw_country,
                        "resort": raw_resort,
                        "price": raw_price,
                        "departure": raw_departure,
                    }
                ),
            )
            failed += 1
            continue

        tour_id = find_existing_tour(cur, operator_id, hotel_id, departure, nights, meal_type, adults, children)
        if not tour_id:
            tour_id = create_missing_tour(cur, operator_id, hotel_id, departure, nights, meal_type, price, adults, children)
            created += 1

        ensure_hotel_alias(cur, hotel_id, operator_id, raw_hotel_name, source_name)
        cur.execute(
            """
            UPDATE tours_raw
            SET raw_country = ?, raw_resort = ?, raw_meal = ?, tour_id = ?, is_processed = 1, error_type = NULL
            WHERE id = ?
            """,
            (country_name, resort_name, meal_type, tour_id, raw_id),
        )
        processed += 1

    conn.commit()
    print(f"  [OK] Обработано сырых туров: {processed}")
    print(f"  [OK] Создано новых нормализованных туров: {created}")
    print(f"  [INFO] Ошибочных записей осталось: {failed}")


def deduplicate_hotels(conn, threshold=0.88, auto_merge_threshold=0.97):
    cur = conn.cursor()
    cur.execute("DELETE FROM hotel_duplicates")
    cur.execute(
        """
        SELECT h1.id, h1.name, h1.resort_id, h2.id, h2.name, h2.resort_id
        FROM hotels h1
        JOIN hotels h2 ON h1.resort_id = h2.resort_id AND h1.id < h2.id
        """
    )
    pairs = cur.fetchall()
    potential = 0
    auto_merged = 0
    manual = 0

    for hotel_1, name_1, _resort_1, hotel_2, name_2, _resort_2 in pairs:
        similarity = SequenceMatcher(None, name_1.lower(), name_2.lower()).ratio()
        if similarity < threshold:
            continue
        status = "merged" if similarity >= auto_merge_threshold else "pending"
        cur.execute(
            """
            INSERT INTO hotel_duplicates (hotel_id_1, hotel_id_2, similarity, status)
            VALUES (?, ?, ?, ?)
            """,
            (hotel_1, hotel_2, round(similarity, 4), status),
        )
        if status == "merged":
            cur.execute("UPDATE tours SET hotel_id = ? WHERE hotel_id = ?", (hotel_1, hotel_2))
            cur.execute("UPDATE hotels_raw SET hotel_id = ? WHERE hotel_id = ?", (hotel_1, hotel_2))
            cur.execute("UPDATE hotel_aliases SET hotel_id = ? WHERE hotel_id = ?", (hotel_1, hotel_2))
            auto_merged += 1
        else:
            manual += 1
        potential += 1

    conn.commit()
    print(f"  [OK] Потенциальные дубликаты отелей: {potential}")
    print(f"       Автоматически объединены: {auto_merged}")
    print(f"       Требуют ручного разбора: {manual}")


def deduplicate_tours(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT operator_id, hotel_id, departure_date, meal_type, adults, children,
               GROUP_CONCAT(id), COUNT(*), MIN(actual_price)
        FROM tours
        GROUP BY operator_id, hotel_id, departure_date, meal_type, adults, children
        HAVING COUNT(*) > 1
        """
    )
    rows = cur.fetchall()
    removed = 0
    for operator_id, hotel_id, departure_date, meal_type, adults, children, ids_str, _count, min_price in rows:
        ids = [int(item) for item in ids_str.split(",")]
        cur.execute(
            """
            SELECT id FROM tours
            WHERE operator_id = ? AND hotel_id = ? AND departure_date = ? AND meal_type = ?
              AND adults = ? AND children = ? AND actual_price = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (operator_id, hotel_id, departure_date, meal_type, adults, children, min_price),
        )
        keep_id = cur.fetchone()[0]
        for tour_id in ids:
            if tour_id != keep_id:
                cur.execute("UPDATE tours SET is_available = 0 WHERE id = ?", (tour_id,))
                removed += 1

    conn.commit()
    print(f"  [OK] Дубликатов туров помечено как недоступные: {removed}")


def normalize_all():
    if not os.path.exists(DB_PATH):
        print("[ERROR] База данных не найдена. Сначала запустите 01_generate_data.py")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    print("[1/4] Нормализация сырых отелей...")
    normalize_raw_hotels(conn)

    print("[2/4] Нормализация сырых туров...")
    normalize_raw_tours(conn)

    print("[3/4] Дедупликация отелей...")
    deduplicate_hotels(conn)

    print("[4/4] Дедупликация туров...")
    deduplicate_tours(conn)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM hotels_raw WHERE is_processed = 1")
    processed_hotels = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tours_raw WHERE is_processed = 1")
    processed_tours = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tours_raw WHERE is_processed = 0")
    pending_tours = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM hotel_duplicates WHERE status = 'pending'")
    pending_duplicates = cur.fetchone()[0]

    print("\nИтоги нормализации")
    print("-------------------")
    print(f"  Обработано raw-отелей: {processed_hotels}")
    print(f"  Обработано raw-туров: {processed_tours}")
    print(f"  Осталось проблемных raw-туров: {pending_tours}")
    print(f"  Дубликатов отелей на ручной разбор: {pending_duplicates}")

    conn.close()
    print("[READY] Нормализация завершена")


if __name__ == "__main__":
    normalize_all()
