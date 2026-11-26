"""Мониторинг уровня заработных плат.

    python main.py init              создать Excel-файл с настройками
    python main.py run               собрать данные и обновить отчёт в Excel
    python main.py run --open        то же и открыть файл
    python main.py schedule          запускать мониторинг автоматически (Windows)
    python main.py unschedule        отключить автоматический запуск
"""
import argparse
import datetime
import logging
import os
import subprocess
import sys

from vacancy_monitor import pipeline
from vacancy_monitor.sources import SOURCES, build_sources
from vacancy_monitor.storage import Storage
from vacancy_monitor.workbook import WorkbookLocked, create_template, read_config, write_report

DEFAULT_FILE = "Мониторинг зарплат.xlsx"
TASK_NAME = "Мониторинг зарплат"
USER_AGENT = os.environ.get("VACANCY_USER_AGENT", "SalaryMonitor/1.0")


def cmd_init(args):
    if os.path.exists(args.file) and not args.force:
        print(f"Файл уже есть: {os.path.abspath(args.file)}")
        print("Чтобы создать заново (настройки будут потеряны), добавьте --force")
        return 1
    create_template(args.file)
    print(f"Создан файл: {os.path.abspath(args.file)}")
    print("Заполните вкладки «Настройки мониторинга» и «Наша зп», затем выполните: python main.py run")
    return 0


def cmd_run(args):
    if not os.path.exists(args.file):
        print(f"Нет файла {args.file}. Сначала выполните: python main.py init")
        return 1
    config = read_config(args.file)
    targets, params = config["targets"], config["params"]
    if not targets:
        print("В «Настройках мониторинга» нет ни одной включённой должности")
        return 1
    unknown = [s for s in params["sources"] if s not in SOURCES]
    if unknown:
        print(f"Неизвестные источники: {', '.join(unknown)}. Доступны: {', '.join(SOURCES)}")
        return 1
    sources = [s for s in build_sources(params["sources"], USER_AGENT) if s.is_available()]
    skipped = set(params["sources"]) - {s.name for s in sources}
    if skipped:
        print(f"Пропущены (нет ключа API): {', '.join(sorted(skipped))}")
    if not sources:
        print("Нет доступных источников")
        return 1

    print(f"Должностей и локаций: {len(targets)}, источники: {', '.join(s.title for s in sources)}")
    raw, worked = pipeline.collect(targets, sources, params["limit"])
    result = pipeline.process(raw, targets, config["dictionary"], config["our_pay"], params["min_sample"])
    result["sources"] = [pipeline.SOURCE_TITLES.get(s, s) for s in worked]

    storage = Storage(args.db)
    storage.save_run(result["date"], worked, result["stats"])
    history = storage.history()
    for h in history:
        h["date"] = datetime.date.fromisoformat(h["date"])

    try:
        write_report(args.file, result, history, result["new_synonyms"])
    except WorkbookLocked as exc:
        print(exc)
        return 1

    d = result["dropped_detail"]
    print(f"\nСобрано вакансий: {len(raw)}")
    print(f"В расчёте: {len(result['used'])}, в «Прочее»: {len(result['other'])}")
    print(f"Отсеяно: повторы {d['повтор']}, военная служба {d['военная служба']}, "
          f"ошибки в зарплате {d['ошибка в зарплате']}, выбросы {d['выброс']}, без зарплаты {d['без зарплаты']}")
    if result["new_synonyms"]:
        print(f"В словарь добавлено новых названий для проверки: {len(result['new_synonyms'])}")
    print(f"\nОтчёт обновлён: {os.path.abspath(args.file)}")
    if args.open and sys.platform == "win32":
        os.startfile(os.path.abspath(args.file))
    return 0


def cmd_schedule(args):
    if sys.platform != "win32":
        print("Автоматический запуск настраивается только в Windows")
        return 1
    period = str(read_config(args.file)["params"]["period"]).lower() if os.path.exists(args.file) else ""
    folder = os.path.dirname(os.path.abspath(__file__))
    command = f'cmd /c cd /d "{folder}" && "{sys.executable}" main.py run --file "{os.path.abspath(args.file)}"'
    if period.startswith("ежемес"):
        when = ["/SC", "MONTHLY", "/D", "1"]
        text = "каждое 1-е число месяца"
    else:
        when = ["/SC", "WEEKLY", "/D", "MON"]
        text = "каждый понедельник"
    cmd = ["schtasks", "/Create", "/F", "/TN", TASK_NAME, "/TR", command, *when, "/ST", args.time]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout or res.stderr)
        return 1
    print(f"Готово: мониторинг будет запускаться {text} в {args.time} (компьютер должен быть включён)")
    print("Изменить периодичность: поле «Периодичность» в настройках, затем снова python main.py schedule")
    return 0


def cmd_unschedule(args):
    res = subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], capture_output=True, text=True)
    print("Автоматический запуск отключён" if res.returncode == 0 else (res.stdout or res.stderr))
    return res.returncode


def main():
    parser = argparse.ArgumentParser(description="Мониторинг уровня заработных плат")
    parser.add_argument("--file", default=DEFAULT_FILE, help="Excel-файл мониторинга")
    parser.add_argument("--db", default="data/history.db", help="база истории замеров")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="создать Excel-файл с настройками")
    p.add_argument("--force", action="store_true", help="перезаписать существующий файл")
    p = sub.add_parser("run", help="собрать данные и обновить отчёт")
    p.add_argument("--open", action="store_true", help="открыть файл после обновления")
    p = sub.add_parser("schedule", help="автоматический запуск по расписанию (Windows)")
    p.add_argument("--time", default="09:00", help="время запуска, по умолчанию 09:00")
    sub.add_parser("unschedule", help="отключить автоматический запуск")

    # --file и --db можно писать и после команды
    for action in list(parser._actions):
        if action.dest in ("file", "db"):
            for subparser in sub.choices.values():
                subparser.add_argument(f"--{action.dest}", default=argparse.SUPPRESS, help=action.help)

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    handlers = {"init": cmd_init, "run": cmd_run, "schedule": cmd_schedule, "unschedule": cmd_unschedule}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
