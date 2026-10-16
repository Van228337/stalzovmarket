"""STALCRAFT Market Scanner - Easy Launcher.

Usage:
  python run.py           # Запустить один цикл сбора и анализа рынка
  python run.py --loop    # Запустить непрерывный цикл мониторинга каждые 5 минут
  python run.py --web     # Запустить локальный веб-дашборд (порт 8000)
  python run.py --test    # Запустить проверку соединения и каналов (Фаза 0)
"""

import argparse
import asyncio
import http.server
import os
from pathlib import Path
import socketserver
import sys
import time
import webbrowser
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run_cycle_once():
    from collector.runner import CollectorRunner
    runner = CollectorRunner()
    asyncio.run(runner.initialize())
    return asyncio.run(runner.run_cycle(dry_run=True))


def run_continuous_loop(interval_min: int = 5):
    print(f"🚀 Запуск непрерывного мониторинга аукциона STALCRAFT (интервал: {interval_min} мин)...")
    print("Для остановки нажмите Ctrl+C\n")
    from collector.runner import CollectorRunner
    runner = CollectorRunner()
    asyncio.run(runner.initialize())

    while True:
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Старт цикла сбора данных...")
            asyncio.run(runner.run_cycle(dry_run=True))
            print(f"[{time.strftime('%H:%M:%S')}] Цикл завершён. Следующий через {interval_min} мин.\n")
            time.sleep(interval_min * 60)
        except KeyboardInterrupt:
            print("\nМониторинг остановлен пользователем.")
            break
        except Exception as e:
            print(f"Ошибка в цикле: {e}. Повтор через 60 секунд.")
            time.sleep(60)


def run_web_dashboard(port: int = 8000):
    os.chdir(PROJECT_ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    print(f"🌐 Запуск локального веб-сервера на http://localhost:{port}/web/")
    webbrowser.open(f"http://localhost:{port}/web/")

    with socketserver.TCPServer(("", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nВеб-сервер остановлен.")


def run_test():
    from collector.test_channel import main as test_main
    asyncio.run(test_main())


def main():
    parser = argparse.ArgumentParser(description="STALCRAFT Market Scanner Launcher")
    parser.add_argument("--loop", action="store_true", help="Запуск непрерывного цикла мониторинга каждые 5 минут")
    parser.add_argument("--web", action="store_true", help="Запуск локального веб-дашборда")
    parser.add_argument("--test", action="store_true", help="Проверка подключения и каналов API")
    parser.add_argument("--interval", type=int, default=5, help="Интервал в минутах для --loop (по умолчанию 5)")
    args = parser.parse_args()

    if args.test:
        run_test()
    elif args.web:
        run_web_dashboard()
    elif args.loop:
        run_continuous_loop(args.interval)
    else:
        run_cycle_once()


if __name__ == "__main__":
    main()
