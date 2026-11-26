"""Excel-файл мониторинга: настройки, ручные данные и отчёт в одной книге.

Вкладки, которые заполняет человек (программа их только читает):
  «Настройки мониторинга» - должности, локации, параметры сбора
  «Наша зп»               - вилки зарплат банка
  «Словарь должностей»    - соответствия названий (программа дописывает «авто»)

Вкладки, которые программа пересоздаёт при каждом запуске:
  «Отчёт», «Дашборд», «Прочее (не по конфигурации)», «Вакансии»
"""
import os

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

SETTINGS = "Настройки мониторинга"
OUR_PAY = "Наша зп"  # символ «/» в названии вкладки Excel запрещён
DICTIONARY = "Словарь должностей"
REPORT = "Отчёт"
DASHBOARD = "Дашборд"
OTHER = "Прочее (не по конфигурации)"
VACANCIES = "Вакансии"
OUTPUT_SHEETS = [REPORT, DASHBOARD, OTHER, VACANCIES]
SHEET_ORDER = [REPORT, DASHBOARD, SETTINGS, OUR_PAY, DICTIONARY, OTHER, VACANCIES]

STATUS_LOW = "ниже рынка"
STATUS_OK = "в вилке"
STATUS_HIGH = "выше рынка"
STATUS_NONE = "нет данных"

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
MONEY = '# ##0" ₽"'
PERCENT = '+0.0%;-0.0%;0.0%'

# Параметры сбора: название в Excel -> (ключ, значение по умолчанию, подсказка)
PARAMS = [
    ("Источники", "sources", "trudvsem, superjob, hh",
     "через запятую: trudvsem - «Работа России», superjob - SuperJob, hh - HeadHunter"),
    ("Вакансий с каждого сайта", "limit", 100, "на одну должность в одной локации"),
    ("Минимум вакансий для расчёта", "min_sample", 5, "если меньше - показатели не считаются"),
    ("Периодичность", "period", "еженедельно", "еженедельно или ежемесячно (для планировщика)"),
]

DEFAULT_POSITIONS = [
    # должность, поисковый запрос, в дашборд
    ("Аналитик данных", "аналитик данных", "да"),
    ("Специалист по информационной безопасности", "информационной безопасности", "да"),
    ("Python-разработчик", "python разработчик", "да"),
    ("Тестировщик", "тестировщик", "нет"),
    ("Бухгалтер", "бухгалтер", "да"),
    ("Юрист", "юрист", "нет"),
    ("Кредитный специалист", "кредитный специалист", "да"),
    ("Операционист", "операционист", "нет"),
    ("Оператор контакт-центра", "оператор колл-центра", "нет"),
]
DEFAULT_LOCATIONS = ["Москва", "Санкт-Петербург"]

DEFAULT_DICTIONARY = [
    ("Data analyst", "Аналитик данных"),
    ("BI-аналитик", "Аналитик данных"),
    ("Аналитик BI", "Аналитик данных"),
    ("Инженер по информационной безопасности", "Специалист по информационной безопасности"),
    ("Специалист по ИБ", "Специалист по информационной безопасности"),
    ("Специалист по защите информации", "Специалист по информационной безопасности"),
    ("Python developer", "Python-разработчик"),
    ("Разработчик Python", "Python-разработчик"),
    ("Программист Python", "Python-разработчик"),
    ("QA-инженер", "Тестировщик"),
    ("QA engineer", "Тестировщик"),
    ("Инженер по тестированию", "Тестировщик"),
    ("Главный бухгалтер", "не учитывать"),
    ("Помощник юриста", "не учитывать"),
    ("Кредитный эксперт", "Кредитный специалист"),
    ("Кредитный менеджер", "Кредитный специалист"),
    ("Кассир-операционист", "Операционист"),
    ("Оператор call-центра", "Оператор контакт-центра"),
    ("Оператор колл-центра", "Оператор контакт-центра"),
    ("Специалист контакт-центра", "Оператор контакт-центра"),
]


class WorkbookLocked(Exception):
    pass


def _header(ws, row, titles, widths=None):
    for col, title in enumerate(titles, 1):
        cell = ws.cell(row=row, column=col, value=title)
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    if widths:
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(col)].width = width


def _note(ws, cell, text):
    ws[cell] = text
    ws[cell].font = Font(italic=True, color="7F7F7F")


def create_template(path):
    wb = Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet(SETTINGS)
    _header(ws, 1, ["Должность", "Поисковый запрос", "Локация", "Включено", "В дашборд"],
            [42, 32, 20, 11, 11])
    row = 2
    for location in DEFAULT_LOCATIONS:
        for name, query, dash in DEFAULT_POSITIONS:
            for col, value in enumerate([name, query, location, "да", dash], 1):
                ws.cell(row=row, column=col, value=value).fill = INPUT_FILL
            row += 1
    yes_no = DataValidation(type="list", formula1='"да,нет"', allow_blank=True)
    ws.add_data_validation(yes_no)
    yes_no.add("D2:E500")
    for col, title in ((7, "Параметр"), (8, "Значение"), (9, "Подсказка")):
        c = ws.cell(row=1, column=col, value=title)
        c.fill, c.font, c.border = HEADER_FILL, HEADER_FONT, BORDER
    ws.column_dimensions["G"].width = 30
    ws.column_dimensions["H"].width = 26
    ws.column_dimensions["I"].width = 60
    for i, (title, _key, value, hint) in enumerate(PARAMS, 2):
        ws.cell(row=i, column=7, value=title)
        ws.cell(row=i, column=8, value=value).fill = INPUT_FILL
        ws.cell(row=i, column=9, value=hint).font = Font(color="7F7F7F")
    _note(ws, "G8", "Жёлтые ячейки можно менять. Одна строка слева - одна должность в одной локации.")
    _note(ws, "G9", "Локация «Россия» - поиск по всей стране. Поисковый запрос можно не заполнять.")
    ws.freeze_panes = "A2"

    ws = wb.create_sheet(OUR_PAY)
    _header(ws, 1, ["Должность", "Локация", "Вилка мин, ₽", "Вилка макс, ₽", "Дата обновления"],
            [42, 20, 16, 16, 18])
    _note(ws, "G1", "Заполняется вручную. Названия должностей - как в «Настройках мониторинга».")
    _note(ws, "G2", "Строки ниже - пример, замените цифрами банка.")
    examples = [("Аналитик данных", "Москва", 150000, 220000),
                ("Бухгалтер", "Москва", 80000, 110000),
                ("Операционист", "Москва", 55000, 70000)]
    for r, values in enumerate(examples, 2):
        for c, value in enumerate(values, 1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.fill = INPUT_FILL
            if c in (3, 4):
                cell.number_format = MONEY
    ws.freeze_panes = "A2"

    ws = wb.create_sheet(DICTIONARY)
    _header(ws, 1, ["Название в вакансиях", "Единая должность", "Добавлено"], [45, 42, 22])
    for r, (synonym, position) in enumerate(DEFAULT_DICTIONARY, 2):
        ws.cell(row=r, column=1, value=synonym).fill = INPUT_FILL
        ws.cell(row=r, column=2, value=position).fill = INPUT_FILL
        ws.cell(row=r, column=3, value="вручную")
    _note(ws, "E1", "Если название вакансии содержит фразу из столбца A, должность берётся из столбца B.")
    _note(ws, "E2", "«не учитывать» в столбце B - такие вакансии попадут в «Прочее».")
    _note(ws, "E3", "Строки «авто (проверить)» добавила программа: проверьте и исправьте при необходимости.")
    ws.auto_filter.ref = "A1:C1"
    ws.freeze_panes = "A2"

    save(wb, path)


def save(wb, path):
    for i, name in enumerate([n for n in SHEET_ORDER if n in wb.sheetnames]):
        wb.move_sheet(name, offset=i - wb.sheetnames.index(name))
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    try:
        wb.save(path)
    except PermissionError as exc:
        raise WorkbookLocked(f"Не удалось сохранить {path}: закройте файл в Excel и запустите снова") from exc


def _text(value):
    return str(value).strip() if value is not None else ""


def _number(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(" ", "").replace("\xa0", "").replace(",", "."))
    except ValueError:
        return None


def _yes(value, default=True):
    text = _text(value).lower()
    if not text:
        return default
    return text in ("да", "yes", "1", "+", "true", "вкл")


def read_config(path):
    wb = load_workbook(path)
    for name in (SETTINGS, OUR_PAY, DICTIONARY):
        if name not in wb.sheetnames:
            raise ValueError(f"В файле {path} нет вкладки «{name}». Создайте новый файл командой init")

    ws = wb[SETTINGS]
    targets = []
    for row in ws.iter_rows(min_row=2, max_col=5, values_only=True):
        name, query, location, enabled, dash = row
        if not _text(name):
            continue
        if not _yes(enabled):
            continue
        targets.append({
            "position": _text(name),
            "query": _text(query) or _text(name),
            "location": _text(location) or "Россия",
            "dashboard": _yes(dash, default=False),
        })
    params = {key: default for _title, key, default, _hint in PARAMS}
    titles = {title.lower(): key for title, key, _d, _h in PARAMS}
    for title, value in ws.iter_rows(min_row=2, min_col=7, max_col=8, values_only=True):
        key = titles.get(_text(title).lower())
        if key and value not in (None, ""):
            params[key] = value
    params["sources"] = [s.strip().lower() for s in str(params["sources"]).split(",") if s.strip()]
    for key in ("limit", "min_sample"):
        params[key] = int(_number(params[key]) or 0) or dict((k, d) for _t, k, d, _h in PARAMS)[key]

    our_pay = {}
    for row in wb[OUR_PAY].iter_rows(min_row=2, max_col=5, values_only=True):
        name, location, low, high, updated = row
        if _text(name):
            our_pay[(_text(name).lower(), (_text(location) or "Россия").lower())] = {
                "min": _number(low), "max": _number(high), "updated": updated,
            }

    dictionary = []
    for row in wb[DICTIONARY].iter_rows(min_row=2, max_col=2, values_only=True):
        if _text(row[0]) and _text(row[1]):
            dictionary.append((_text(row[0]), _text(row[1])))

    return {"targets": targets, "params": params, "our_pay": our_pay, "dictionary": dictionary}


def compare(median, pay):
    """Сравнение медианы рынка с вилкой банка: (отклонение, статус)."""
    if not median or not pay or not (pay.get("min") or pay.get("max")):
        return None, STATUS_NONE if median else ""
    low = pay.get("min") or pay.get("max")
    high = pay.get("max") or pay.get("min")
    deviation = ((low + high) / 2 - median) / median
    if median > high:
        status = STATUS_LOW      # рынок платит больше верхней границы нашей вилки
    elif median < low:
        status = STATUS_HIGH     # рынок платит меньше нижней границы нашей вилки
    else:
        status = STATUS_OK
    return deviation, status


def _table(ws, titles, rows, widths, money_cols=(), percent_cols=(), date_cols=()):
    _header(ws, 1, titles, widths)
    for r, values in enumerate(rows, 2):
        for c, value in enumerate(values, 1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.border = BORDER
            if c in money_cols:
                cell.number_format = MONEY
            elif c in percent_cols:
                cell.number_format = PERCENT
            elif c in date_cols:
                cell.number_format = "DD.MM.YYYY"
    last = get_column_letter(len(titles))
    ws.auto_filter.ref = f"A1:{last}{max(1, len(rows) + 1)}"
    ws.freeze_panes = "A2"


def write_report(path, result, history, new_synonyms):
    wb = load_workbook(path)
    for name in OUTPUT_SHEETS:
        if name in wb.sheetnames:
            del wb[name]

    # «Отчёт»
    ws = wb.create_sheet(REPORT)
    rows = []
    for s in result["stats"]:
        rows.append([
            s["position"], s["location"], s["median"], s["p25"], s["p75"], s["count"],
            s["sources"], s["by_source"], result["date"], s["our_min"], s["our_max"],
            s["deviation"], s["status"],
        ])
    _table(ws, ["Должность", "Локация", "Медиана", "25 перцентиль", "75 перцентиль",
                "Вакансий с з/п", "Источник", "Медиана по источникам", "Дата актуальности",
                "Наша вилка мин", "Наша вилка макс", "Отклонение (наша з/п от медианы)", "Статус"],
           rows, [36, 16, 13, 13, 13, 10, 22, 34, 13, 13, 13, 16, 14],
           money_cols=(3, 4, 5, 10, 11), percent_cols=(12,), date_cols=(9,))
    n = len(rows) + 1
    for status, color in ((STATUS_LOW, "F8CBAD"), (STATUS_OK, "C6EFCE"), (STATUS_HIGH, "BDD7EE")):
        ws.conditional_formatting.add(
            f"M2:M{n}", CellIsRule(operator="equal", formula=[f'"{status}"'],
                                   fill=PatternFill("solid", fgColor=color)))

    # «Прочее / Не по конфигурации»
    ws = wb.create_sheet(OTHER)
    _table(ws, ["Название вакансии", "Искали как", "Локация поиска", "Регион вакансии", "Зарплата",
                "Работодатель", "Источник", "Причина", "Ссылка"],
           [[v["title"], v["target_position"], v["target_location"], v["region"], v["salary_rub"],
             v["employer"], v["source"], v["reason"], v["url"]] for v in result["other"]],
           [45, 30, 16, 22, 13, 30, 11, 30, 40], money_cols=(5,))

    # «Вакансии» - всё, что вошло в расчёт, для проверки
    ws = wb.create_sheet(VACANCIES)
    _table(ws, ["Должность", "Локация", "Название вакансии", "Как определена должность", "Зарплата",
                "От", "До", "Работодатель", "Регион", "Опыт", "Источник", "Ссылка"],
           [[v["position"], v["target_location"], v["title"], v["match"], v["salary_rub"],
             v["salary_from"], v["salary_to"], v["employer"], v["region"], v["experience"],
             v["source"], v["url"]] for v in result["used"]],
           [32, 14, 45, 16, 13, 11, 11, 30, 22, 14, 11, 40], money_cols=(5,))

    _write_dashboard(wb.create_sheet(DASHBOARD), result, history)

    if new_synonyms:
        ws = wb[DICTIONARY]
        existing = {_text(c.value).lower() for c in ws["A"] if c.value}
        row = ws.max_row + 1
        for title, position in new_synonyms:
            if title.lower() in existing:
                continue
            ws.cell(row=row, column=1, value=title).fill = INPUT_FILL
            ws.cell(row=row, column=2, value=position).fill = INPUT_FILL
            ws.cell(row=row, column=3, value=f"авто (проверить) {result['date']:%d.%m.%Y}")
            existing.add(title.lower())
            row += 1

    save(wb, path)


def _write_dashboard(ws, result, history):
    ws.column_dimensions["A"].width = 40
    for col in "BCDEFGHIJKLM":
        ws.column_dimensions[col].width = 15
    ws["A1"] = "Мониторинг уровня заработных плат"
    ws["A1"].font = Font(bold=True, size=16)
    ws["A2"] = (f"Дата актуальности: {result['date']:%d.%m.%Y} · источники: {', '.join(result['sources'])}"
                f" · вакансий в расчёте: {len(result['used'])} · отсеяно ошибок и дублей: {result['dropped']}")
    ws["A2"].font = Font(color="7F7F7F")

    stats = result["stats"]
    counts = {s: sum(1 for x in stats if x["status"] == s) for s in (STATUS_LOW, STATUS_OK, STATUS_HIGH)}
    kpis = [("Позиций в отчёте", len(stats)), ("Ниже рынка", counts[STATUS_LOW]),
            ("В вилке", counts[STATUS_OK]), ("Выше рынка", counts[STATUS_HIGH])]
    for col, (title, value) in zip((1, 3, 5, 7), kpis):
        ws.cell(row=4, column=col, value=title).font = Font(color="7F7F7F")
        ws.cell(row=5, column=col, value=value).font = Font(bold=True, size=18)

    # Текущая медиана рынка и наша вилка по ролям для дашборда
    roles = [s for s in stats if s["dashboard"] and s["median"]]
    ws["A7"] = "Рынок и наша вилка (роли из «Настроек мониторинга»)"
    ws["A7"].font = Font(bold=True, size=13)
    _header_row(ws, 8, ["Роль", "25 перцентиль", "Медиана", "75 перцентиль", "Наша вилка мин",
                        "Наша вилка макс", "Статус"])
    for r, s in enumerate(roles, 9):
        values = [f"{s['position']} ({s['location']})", s["p25"], s["median"], s["p75"],
                  s["our_min"], s["our_max"], s["status"]]
        for c, value in enumerate(values, 1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.border = BORDER
            if 2 <= c <= 6:
                cell.number_format = MONEY
    end = 8 + len(roles)
    if roles:
        chart = BarChart()
        chart.title = "Медиана рынка и наша вилка"
        chart.y_axis.title = "₽"
        chart.height, chart.width = 11, 24
        chart.add_data(Reference(ws, min_col=3, max_col=3, min_row=8, max_row=end), titles_from_data=True)
        chart.add_data(Reference(ws, min_col=5, max_col=6, min_row=8, max_row=end), titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=1, min_row=9, max_row=end))
        ws.add_chart(chart, f"I{8}")

    # Динамика медианы по ролям: роли по строкам, замеры по столбцам
    start = max(end + 3, 27)
    ws.cell(row=start, column=1, value="Динамика медианы зарплаты по ролям").font = Font(bold=True, size=13)
    role_keys = [(s["position"], s["location"]) for s in roles]
    dates = sorted({h["date"] for h in history})
    _header_row(ws, start + 1, ["Роль"] + [d.strftime("%d.%m.%Y") for d in dates])
    by_key = {(h["date"], h["position"], h["location"]): h["median"] for h in history}
    for r, key in enumerate(role_keys, start + 2):
        ws.cell(row=r, column=1, value=f"{key[0]} ({key[1]})").border = BORDER
        for c, day in enumerate(dates, 2):
            cell = ws.cell(row=r, column=c, value=by_key.get((day, *key)))
            cell.number_format, cell.border = MONEY, BORDER
    last_row = start + 1 + len(role_keys)
    if role_keys and dates:
        chart = LineChart()
        chart.title = "Медиана по замерам"
        chart.y_axis.title = "₽"
        chart.height, chart.width = 10, 26
        chart.add_data(Reference(ws, min_col=1, max_col=1 + len(dates), min_row=start + 2, max_row=last_row),
                       from_rows=True, titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=2, max_col=1 + len(dates), min_row=start + 1))
        ws.add_chart(chart, f"A{last_row + 6}")
        if len(dates) < 2:
            ws.cell(row=last_row + 1, column=1,
                    value="Линии появятся после второго замера").font = Font(italic=True, color="7F7F7F")


def _header_row(ws, row, titles):
    for c, title in enumerate(titles, 1):
        cell = ws.cell(row=row, column=c, value=title)
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
        cell.alignment = Alignment(wrap_text=True, vertical="center")
