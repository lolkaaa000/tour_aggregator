#!/usr/bin/env python3
"""
ТУРАГРЕГАТОР: Главный оркестратор
Запускает полный цикл:
  1. Генерация данных (БД + справочники + тестовые данные)
  2. Нормализация и дедупликация
  3. Проверка качества данных
  4. Визуализации (PNG графики)
  5. Тесты (pytest)

Запуск: python main.py
"""

import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_step(name, command, cwd=None):
    """Выполнить один шаг с выводом результата."""
    print(f"\n{name}")
    print("-" * 60)
    result = subprocess.run(command, cwd=cwd or BASE_DIR, shell=False)
    if result.returncode != 0:
        print(f"\nОшибка: шаг '{name}' завершён с кодом {result.returncode}")
        return False
    print(f"\nГотово: шаг '{name}' завершён успешно")
    return True


def main():
    print("Турагрегатор: полный цикл обработки данных")
    print("-" * 60)

    steps = [
        ("1. Генерация данных", [sys.executable, "scripts/01_generate_data.py"]),
        ("2. Нормализация и дедупликация", [sys.executable, "scripts/02_normalize_data.py"]),
        ("3. Проверка качества данных", [sys.executable, "scripts/03_data_quality.py"]),
        ("4. Визуализации (PNG)", [sys.executable, "scripts/04_visualizations.py"]),
        ("5. Тесты (pytest)", [sys.executable, "-m", "pytest", "tests/test_tour_aggregator.py", "-v", "--tb=short"]),
    ]

    results = {}
    for name, command in steps:
        success = run_step(name, command)
        results[name] = "OK" if success else "FAILED"
        if not success:
            print(f"\nОстанавливаем выполнение на шаге: {name}")
            break

    # Итоговый отчёт
    print("\nИтоговый отчёт")
    print("-" * 60)
    for name, status in results.items():
        label = "ok" if status == "OK" else "ошибка"
        print(f"  {name}: {label}")

    all_ok = all(s == "OK" for s in results.values())
    if all_ok:
        print("\nВсе шаги выполнены успешно.")
        print(f"База данных: {os.path.join(BASE_DIR, 'download', 'tour_aggregator.db')}")
        print(f"Графики: {os.path.join(BASE_DIR, 'download', 'chart_*.png')}")
    else:
        print("\nЕсть ошибки. Подробности выше.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
