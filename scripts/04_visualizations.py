#!/usr/bin/env python3
"""Графики по данным турагрегатора."""

import sqlite3
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'download', 'tour_aggregator.db')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'download')

# Настройка шрифтов

# Используем системные шрифты без жёсткой привязки к Linux-пути.
available_fonts = {font.name for font in fm.fontManager.ttflist}
preferred_fonts = ['DejaVu Sans', 'Arial', 'Segoe UI', 'Liberation Sans']
font_candidates = [font for font in preferred_fonts if font in available_fonts]
if not font_candidates:
    font_candidates = ['sans-serif']

plt.rcParams['font.sans-serif'] = font_candidates
plt.rcParams['axes.unicode_minus'] = False

# Цветовая палитра
COLORS = {
    'primary': '#304651',
    'accent': '#238ec3',
    'accent2': '#e8a838',
    'accent3': '#e85d4a',
    'accent4': '#5bb574',
    'accent5': '#9b59b6',
    'bg': '#f5f7fa',
    'grid': '#e0e4e8',
}

PALETTE = ['#238ec3', '#e8a838', '#e85d4a', '#5bb574', '#9b59b6',
           '#3498db', '#e67e22', '#1abc9c', '#f39c12', '#c0392b',
           '#27ae60', '#8e44ad', '#2ecc71', '#d35400', '#16a085',
           '#e74c3c', '#2980b9', '#f1c40f', '#2c3e50', '#7f8c8d']


def get_connection():
    return sqlite3.connect(DB_PATH)


def chart_tours_by_country():
    """1. Количество туров по странам."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.name, COUNT(*) AS cnt
        FROM tours t
        JOIN countries c ON t.country_id = c.id
        WHERE t.is_available = 1
        GROUP BY c.name
        ORDER BY cnt DESC
    """)
    data = cur.fetchall()
    conn.close()

    if not data:
        print("  [SKIP] Нет данных для chart_tours_by_country")
        return

    countries, counts = zip(*data)
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor(COLORS['bg'])
    ax.set_facecolor(COLORS['bg'])

    bars = ax.barh(range(len(countries)), counts, color=PALETTE[:len(countries)], height=0.7, edgecolor='white', linewidth=0.5)
    ax.set_yticks(range(len(countries)))
    ax.set_yticklabels(countries, fontsize=11)
    ax.invert_yaxis()
    ax.set_xlabel('Количество туров', fontsize=12, fontweight='bold')
    ax.set_title('Количество туров по странам', fontsize=16, fontweight='bold', color=COLORS['primary'], pad=15)

    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height() / 2,
                str(count), va='center', fontsize=10, color=COLORS['primary'])

    ax.grid(axis='x', alpha=0.3, color=COLORS['grid'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'chart_tours_by_country.png')
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close()
    print(f"  [OK] {path}")


def chart_conversion_funnel():
    """2. Воронка конверсии: Поиск → Просмотр → Клик → Бронь."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(DISTINCT session_id) FROM search_logs")
    searches = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT session_id) FROM tour_views")
    views = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT session_id) FROM click_logs")
    clicks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT session_id) FROM bookings WHERE session_id IS NOT NULL")
    bookings = cur.fetchone()[0]
    conn.close()

    stages = ['Поиск', 'Просмотр', 'Клик', 'Бронь']
    values = [searches, views, clicks, bookings]
    colors = [COLORS['accent'], COLORS['accent2'], COLORS['accent3'], COLORS['accent4']]

    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor(COLORS['bg'])
    ax.set_facecolor(COLORS['bg'])

    # Воронка (перевёрнутая пирамида)
    max_val = max(values)
    for i, (stage, val, color) in enumerate(zip(stages, values, colors)):
        width = val / max_val * 100
        left = (100 - width) / 2
        bar = ax.barh(len(stages) - 1 - i, width, left=left, height=0.7,
                       color=color, edgecolor='white', linewidth=2, alpha=0.9)
        # Текст на баре
        pct = val / values[0] * 100 if values[0] > 0 else 0
        ax.text(50, len(stages) - 1 - i, f'{stage}\n{val:,} ({pct:.1f}%)',
                ha='center', va='center', fontsize=13, fontweight='bold', color='white')

    # Стрелки конверсии
    for i in range(len(stages) - 1):
        conv = values[i + 1] / values[i] * 100 if values[i] > 0 else 0
        y_pos = len(stages) - 2 - i
        ax.text(102, y_pos + 0.5, f'{conv:.1f}%', ha='left', va='center',
                fontsize=11, color=COLORS['primary'], fontweight='bold')

    ax.set_xlim(-5, 115)
    ax.set_ylim(-0.5, len(stages) - 0.5)
    ax.axis('off')
    ax.set_title('Воронка конверсии', fontsize=16, fontweight='bold',
                  color=COLORS['primary'], pad=20)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'chart_conversion_funnel.png')
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close()
    print(f"  [OK] {path}")


def chart_seasonality():
    """3. Сезонность цен по месяцам."""
    conn = get_connection()
    cur = conn.cursor()

    # Топ-5 стран по количеству туров
    cur.execute("""
        SELECT c.name FROM tours t
        JOIN countries c ON t.country_id = c.id
        WHERE t.is_available = 1
        GROUP BY c.name ORDER BY COUNT(*) DESC LIMIT 5
    """)
    top_countries = [r[0] for r in cur.fetchall()]

    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor(COLORS['bg'])
    ax.set_facecolor(COLORS['bg'])

    months = list(range(6, 13))
    month_labels = ['Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

    for i, country in enumerate(top_countries):
        cur.execute("""
            SELECT CAST(strftime('%m', t.departure_date) AS INTEGER) AS month,
                   ROUND(AVG(t.actual_price), 0) AS avg_price
            FROM tours t
            JOIN countries c ON t.country_id = c.id
            WHERE c.name = ? AND t.is_available = 1
            GROUP BY month
            ORDER BY month
        """, (country,))
        data = cur.fetchall()
        if not data:
            continue
        months_with_data, prices = zip(*data)
        ax.plot(months_with_data, prices, marker='o', linewidth=2.5, markersize=6,
                color=PALETTE[i], label=country, alpha=0.85)

    conn.close()

    ax.set_xticks(months)
    ax.set_xticklabels(month_labels, fontsize=11)
    ax.set_ylabel('Средняя цена (тг.)', fontsize=12, fontweight='bold')
    ax.set_title('Сезонность цен по странам (топ-5)', fontsize=16,
                  fontweight='bold', color=COLORS['primary'], pad=15)
    ax.legend(fontsize=10, loc='upper right', framealpha=0.9)
    ax.grid(axis='both', alpha=0.3, color=COLORS['grid'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'chart_seasonality.png')
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close()
    print(f"  [OK] {path}")


def chart_operator_comparison():
    """4. Сравнение операторов: рыночная доля и средняя цена."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT op.short_name, COUNT(*) AS cnt,
               ROUND(AVG(t.actual_price), 0) AS avg_price,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM tours WHERE is_available = 1), 1) AS share
        FROM tours t
        JOIN tour_operators op ON t.operator_id = op.id
        WHERE t.is_available = 1
        GROUP BY op.short_name
        ORDER BY cnt DESC
    """)
    data = cur.fetchall()
    conn.close()

    if not data:
        print("  [SKIP] Нет данных для chart_operator_comparison")
        return

    operators, counts, avg_prices, shares = zip(*data)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor(COLORS['bg'])

    # Рыночная доля (pie chart)
    ax1.set_facecolor(COLORS['bg'])
    wedges, texts, autotexts = ax1.pie(counts, labels=operators, autopct='%1.1f%%',
                                         colors=PALETTE[:len(operators)], startangle=90,
                                         pctdistance=0.85, wedgeprops=dict(width=0.5, edgecolor='white'))
    for text in autotexts:
        text.set_fontsize(9)
        text.set_fontweight('bold')
    ax1.set_title('Рыночная доля операторов', fontsize=14, fontweight='bold',
                   color=COLORS['primary'], pad=15)

    # Средняя цена (bar chart)
    ax2.set_facecolor(COLORS['bg'])
    bars = ax2.bar(operators, avg_prices, color=PALETTE[:len(operators)],
                    edgecolor='white', linewidth=0.5)
    for bar, price in zip(bars, avg_prices):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 500,
                 f'{int(price):,}', ha='center', va='bottom', fontsize=9,
                 fontweight='bold', color=COLORS['primary'])
    ax2.set_ylabel('Средняя цена (тг.)', fontsize=11, fontweight='bold')
    ax2.set_title('Средняя цена по операторам', fontsize=14, fontweight='bold',
                   color=COLORS['primary'], pad=15)
    ax2.grid(axis='y', alpha=0.3, color=COLORS['grid'])
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    plt.setp(ax2.get_xticklabels(), rotation=30, ha='right')

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'chart_operator_comparison.png')
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close()
    print(f"  [OK] {path}")


def chart_price_distribution():
    """5. Распределение цен по диапазонам."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            CASE
                WHEN actual_price < 40000 THEN 'до 40K'
                WHEN actual_price < 60000 THEN '40-60K'
                WHEN actual_price < 80000 THEN '60-80K'
                WHEN actual_price < 100000 THEN '80-100K'
                WHEN actual_price < 150000 THEN '100-150K'
                WHEN actual_price < 200000 THEN '150-200K'
                ELSE '200K+'
            END AS price_range,
            COUNT(*) AS cnt
        FROM tours
        WHERE is_available = 1
        GROUP BY price_range
        ORDER BY MIN(actual_price)
    """)
    data = cur.fetchall()
    conn.close()

    if not data:
        print("  [SKIP] Нет данных для chart_price_distribution")
        return

    ranges, counts = zip(*data)
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor(COLORS['bg'])
    ax.set_facecolor(COLORS['bg'])

    bars = ax.bar(ranges, counts, color=PALETTE[:len(ranges)], edgecolor='white', linewidth=0.5)
    for bar, count in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                str(count), ha='center', va='bottom', fontsize=11,
                fontweight='bold', color=COLORS['primary'])

    ax.set_xlabel('Ценовой диапазон (тг.)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Количество туров', fontsize=12, fontweight='bold')
    ax.set_title('Распределение туров по ценовым диапазонам', fontsize=16,
                  fontweight='bold', color=COLORS['primary'], pad=15)
    ax.grid(axis='y', alpha=0.3, color=COLORS['grid'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'chart_price_distribution.png')
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close()
    print(f"  [OK] {path}")


def chart_top_resorts():
    """6. Топ-15 курортов по количеству туров."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.name || ' (' || c.name || ')' AS resort_country,
               COUNT(*) AS cnt,
               ROUND(AVG(t.actual_price), 0) AS avg_price
        FROM tours t
        JOIN resorts r ON t.resort_id = r.id
        JOIN countries c ON t.country_id = c.id
        WHERE t.is_available = 1
        GROUP BY resort_country
        ORDER BY cnt DESC
        LIMIT 15
    """)
    data = cur.fetchall()
    conn.close()

    if not data:
        print("  [SKIP] Нет данных для chart_top_resorts")
        return

    resorts, counts, avg_prices = zip(*data)
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor(COLORS['bg'])
    ax.set_facecolor(COLORS['bg'])

    bars = ax.barh(range(len(resorts)), counts, color=PALETTE[:len(resorts)],
                    height=0.7, edgecolor='white', linewidth=0.5)
    ax.set_yticks(range(len(resorts)))
    ax.set_yticklabels(resorts, fontsize=10)
    ax.invert_yaxis()

    for bar, count, price in zip(bars, counts, avg_prices):
        ax.text(bar.get_width() + 3, bar.get_y() + bar.get_height() / 2,
                f'{count} (ср. {int(price):,} тг.)', va='center', fontsize=9,
                color=COLORS['primary'])

    ax.set_xlabel('Количество туров', fontsize=12, fontweight='bold')
    ax.set_title('Топ-15 курортов по количеству туров', fontsize=16,
                  fontweight='bold', color=COLORS['primary'], pad=15)
    ax.grid(axis='x', alpha=0.3, color=COLORS['grid'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'chart_top_resorts.png')
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close()
    print(f"  [OK] {path}")


def chart_data_quality():
    """7. Результаты проверки качества данных."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT check_category, COUNT(*) AS checks,
               SUM(failed_records) AS total_fails,
               ROUND(AVG(fail_pct), 1) AS avg_fail_pct
        FROM data_quality_reports
        GROUP BY check_category
        ORDER BY total_fails DESC
    """)
    data = cur.fetchall()
    conn.close()

    if not data:
        print("  [SKIP] Нет данных для chart_data_quality (запустите 03_data_quality.py)")
        return

    categories, checks, total_fails, avg_fails = zip(*data)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor(COLORS['bg'])

    # Количество проверок по категориям
    ax1.set_facecolor(COLORS['bg'])
    bars1 = ax1.barh(categories, checks, color=PALETTE[:len(categories)],
                      edgecolor='white', height=0.5)
    ax1.set_xlabel('Количество проверок', fontsize=11, fontweight='bold')
    ax1.set_title('Проверки по категориям', fontsize=14, fontweight='bold',
                   color=COLORS['primary'], pad=15)
    ax1.invert_yaxis()
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    for bar, val in zip(bars1, checks):
        ax1.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                 str(val), va='center', fontsize=10, color=COLORS['primary'])

    # Ошибки по категориям
    ax2.set_facecolor(COLORS['bg'])
    colors2 = [COLORS['accent4'] if f == 0 else COLORS['accent3'] for f in total_fails]
    bars2 = ax2.barh(categories, total_fails, color=colors2, edgecolor='white', height=0.5)
    ax2.set_xlabel('Количество ошибок', fontsize=11, fontweight='bold')
    ax2.set_title('Ошибки по категориям', fontsize=14, fontweight='bold',
                   color=COLORS['primary'], pad=15)
    ax2.invert_yaxis()
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    for bar, val in zip(bars2, total_fails):
        ax2.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                 str(val), va='center', fontsize=10, color=COLORS['primary'])

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'chart_data_quality.png')
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close()
    print(f"  [OK] {path}")


def chart_booking_status():
    """8. Статусы бронирований."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT status, COUNT(*) AS cnt, ROUND(AVG(total_price), 0) AS avg_price
        FROM bookings
        GROUP BY status
        ORDER BY cnt DESC
    """)
    data = cur.fetchall()
    conn.close()

    if not data:
        print("  [SKIP] Нет данных для chart_booking_status")
        return

    statuses, counts, avg_prices = zip(*data)
    status_colors = {
        'confirmed': COLORS['accent4'],
        'pending': COLORS['accent2'],
        'cancelled': COLORS['accent3'],
        'completed': COLORS['accent'],
    }
    colors = [status_colors.get(s, COLORS['accent5']) for s in statuses]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
    fig.patch.set_facecolor(COLORS['bg'])

    # Pie chart
    ax1.set_facecolor(COLORS['bg'])
    wedges, texts, autotexts = ax1.pie(counts, labels=statuses, autopct='%1.1f%%',
                                         colors=colors, startangle=90,
                                         wedgeprops=dict(edgecolor='white', linewidth=2))
    for t in autotexts:
        t.set_fontsize(11)
        t.set_fontweight('bold')
    ax1.set_title('Распределение статусов', fontsize=14, fontweight='bold',
                   color=COLORS['primary'], pad=15)

    # Bar chart со средней ценой
    ax2.set_facecolor(COLORS['bg'])
    bars = ax2.bar(statuses, avg_prices, color=colors, edgecolor='white', linewidth=0.5)
    for bar, price in zip(bars, avg_prices):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 500,
                 f'{int(price):,}', ha='center', va='bottom', fontsize=10,
                 fontweight='bold', color=COLORS['primary'])
    ax2.set_ylabel('Средняя цена (тг.)', fontsize=11, fontweight='bold')
    ax2.set_title('Средняя цена по статусам', fontsize=14, fontweight='bold',
                   color=COLORS['primary'], pad=15)
    ax2.grid(axis='y', alpha=0.3, color=COLORS['grid'])
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'chart_booking_status.png')
    plt.savefig(path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close()
    print(f"  [OK] {path}")


def generate_all_charts():
    """Генерация всех 8 графиков."""
    if not os.path.exists(DB_PATH):
        print("[ERROR] База данных не найдена. Сначала запустите 01_generate_data.py")
        return

    print("=== ГЕНЕРАЦИЯ ВИЗУАЛИЗАЦИЙ ===\n")

    chart_tours_by_country()
    chart_conversion_funnel()
    chart_seasonality()
    chart_operator_comparison()
    chart_price_distribution()
    chart_top_resorts()
    chart_data_quality()
    chart_booking_status()

    print(f"\n[READY] Все графики сохранены в {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_all_charts()
