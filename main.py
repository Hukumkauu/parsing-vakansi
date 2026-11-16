"""Мониторинг рынка труда для профориентации.

Примеры запуска:
    python main.py collect                         # собрать вакансии по всем профессиям (вся Россия)
    python main.py collect --region москва --limit 300
    python main.py collect --sphere IT --sphere "Информационная безопасность"
    python main.py collect --sources hh trudvsem --hh-details 30
    python main.py report                          # сделать HTML-отчёт по последнему замеру
    python main.py stats                           # краткая сводка в консоли
    python main.py list                            # список профессий в каталоге
"""
import argparse
import logging
import os
import sys
import webbrowser

from vacancy_monitor.analytics import market_stats, start_score
from vacancy_monitor.collector import collect
from vacancy_monitor.professions import load_professions, select_professions
from vacancy_monitor.report import build_html, export_csv, export_json
from vacancy_monitor.sources import SOURCES, build_sources
from vacancy_monitor.storage import Storage

USER_AGENT = os.environ.get("VACANCY_USER_AGENT", "CareerMarketMonitor/1.0 (student project)")


def make_report(storage, professions, out_dir, open_browser=False):
    run = storage.last_run()
    if run is None:
        print("В базе ещё нет данных. Сначала выполните: python main.py collect")
        return None
    vacancies = storage.vacancies_for_run(run["id"])
    stats = market_stats(vacancies, professions, storage.totals_for_run(run["id"]))
    stamp = run["started_at"][:10]
    html_path = build_html(stats, storage.history(), run, os.path.join(out_dir, f"report_{stamp}.html"))
    csv_path = export_csv(vacancies, os.path.join(out_dir, f"vacancies_{stamp}.csv"))
    json_path = export_json(stats, os.path.join(out_dir, f"stats_{stamp}.json"))
    print(f"Отчёт:      {os.path.abspath(html_path)}")
    print(f"Вакансии:   {os.path.abspath(csv_path)}")
    print(f"Показатели: {os.path.abspath(json_path)}")
    if open_browser:
        webbrowser.open("file://" + os.path.abspath(html_path))
    return html_path


def print_stats(storage, professions):
    run = storage.last_run()
    if run is None:
        print("В базе ещё нет данных. Сначала выполните: python main.py collect")
        return
    vacancies = storage.vacancies_for_run(run["id"])
    stats = market_stats(vacancies, professions, storage.totals_for_run(run["id"]))
    stats.sort(key=lambda s: s["salary"]["median"] or 0, reverse=True)
    print(f"Замер от {run['started_at']}, регион: {run['region']}\n")
    head = f"{'Профессия':42} {'Вакансий':>9} {'Медиана':>10} {'Без опыта':>10} {'Старт':>6}"
    print(head)
    print("-" * len(head))
    for s in stats:
        med = s["salary"]["median"]
        med = f"{round(med / 1000)} тыс." if med else "—"
        print(f"{s['profession'][:42]:42} {s['found']:>9} {med:>10} "
              f"{round(s['junior_share'] * 100):>9}% {start_score(s):>6}")


def main():
    parser = argparse.ArgumentParser(description="Мониторинг рынка труда для профориентации")
    parser.add_argument("--db", default="data/vacancies.db", help="файл базы данных")
    parser.add_argument("--professions", default="professions.json", help="свой каталог профессий (JSON)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect", help="собрать вакансии")
    p_collect.add_argument("--region", default="россия", help="регион или город (по умолчанию вся Россия)")
    p_collect.add_argument("--limit", type=int, default=200, help="сколько вакансий брать с каждого сайта на профессию")
    p_collect.add_argument("--sources", nargs="+", default=["hh", "trudvsem", "superjob"], choices=list(SOURCES))
    p_collect.add_argument("--profession", action="append", help="только эта профессия (можно часть названия)")
    p_collect.add_argument("--sphere", action="append", help="только эта сфера")
    p_collect.add_argument("--hh-details", type=int, default=20,
                           help="сколько вакансий hh догрузить подробно для точных навыков")
    p_collect.add_argument("--no-report", action="store_true", help="не строить отчёт после сбора")
    p_collect.add_argument("--out", default="reports", help="папка для отчётов")

    p_report = sub.add_parser("report", help="построить отчёт по последнему замеру")
    p_report.add_argument("--out", default="reports", help="папка для отчётов")
    p_report.add_argument("--open", action="store_true", help="открыть отчёт в браузере")

    sub.add_parser("stats", help="сводка в консоли")
    sub.add_parser("list", help="список профессий")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    professions = load_professions(args.professions)

    if args.command == "list":
        for p in professions:
            print(f"{p['sphere']:30} {p['name']:45} запрос: {p['query']}")
        return 0

    storage = Storage(args.db)

    if args.command == "collect":
        chosen = select_professions(professions, args.profession, args.sphere)
        if not chosen:
            print("Не найдено ни одной профессии по фильтру. Посмотрите список: python main.py list")
            return 1
        sources = build_sources(args.sources, USER_AGENT, args.hh_details)
        skipped = [s.title for s in sources if not s.is_available()]
        if skipped:
            print(f"Пропущены (нет ключа API): {', '.join(skipped)}")
        collect(storage, sources, chosen, args.region, args.limit)
        if not args.no_report:
            make_report(storage, professions, args.out)
    elif args.command == "report":
        make_report(storage, professions, args.out, args.open)
    elif args.command == "stats":
        print_stats(storage, professions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
