"""Поиск навыков в тексте вакансии по словарю."""
import re

SKILLS = {
    # Языки и технологии
    "Python": [r"python"], "Java": [r"\bjava\b"], "JavaScript": [r"javascript", r"\bjs\b"],
    "TypeScript": [r"typescript"], "C++": [r"c\+\+"], "C#": [r"c#", r"\.net"],
    "Go": [r"\bgolang\b", r"\bgo\b"], "PHP": [r"\bphp\b"], "Kotlin": [r"kotlin"],
    "SQL": [r"\bsql\b", r"postgres", r"mysql", r"ms sql"], "1С": [r"\b1с\b", r"\b1c\b"],
    "Excel": [r"excel"], "Power BI": [r"power ?bi"], "Git": [r"\bgit\b"],
    "Linux": [r"linux", r"unix"], "Windows Server": [r"windows server"],
    "Docker": [r"docker"], "Kubernetes": [r"kubernetes", r"\bk8s\b"],
    "React": [r"react"], "Vue": [r"\bvue"], "Django": [r"django"], "Spring": [r"spring"],
    "HTML/CSS": [r"\bhtml", r"\bcss\b"], "REST API": [r"\brest\b", r"\bapi\b"],
    "Figma": [r"figma"], "Photoshop": [r"photoshop"], "AutoCAD": [r"autocad", r"автокад"],
    "КОМПАС": [r"компас"], "SolidWorks": [r"solidworks"], "Revit": [r"revit"],
    "Сети (TCP/IP)": [r"tcp/ip", r"\bсет(и|ей|евое)\b", r"cisco", r"маршрутизац"],
    "Машинное обучение": [r"машинн\w* обучени", r"machine learning", r"\bml\b"],
    # Информационная безопасность
    "SIEM": [r"\bsiem\b"], "DLP": [r"\bdlp\b"], "Пентест": [r"пентест", r"pentest", r"тестирован\w* на проникновение"],
    "ФСТЭК/152-ФЗ": [r"фстэк", r"152-фз", r"187-фз", r"кии\b"],
    "Криптография": [r"криптограф", r"скзи"], "Kali Linux": [r"kali"],
    "Анализ уязвимостей": [r"уязвимост"], "SOC": [r"\bsoc\b"],
    # Общие и гибкие навыки
    "Английский язык": [r"английск", r"english"], "Коммуникабельность": [r"коммуникабельн"],
    "Работа в команде": [r"работ\w* в команде", r"командн"],
    "Грамотная речь": [r"грамотн\w* речь"], "Ответственность": [r"ответственн"],
    "Обучаемость": [r"обучаем", r"готовность учиться"],
    "Водительские права": [r"водительск\w* (права|удостоверени)", r"права категори"],
    "Медкнижка": [r"медкниж", r"медицинск\w* книжк"],
    "Высшее образование": [r"высшее\b", r"высшего образования"],
    "Среднее профессиональное": [r"среднее профессиональное", r"среднее специальное", r"\bспо\b"],
    "CRM": [r"\bcrm\b", r"битрикс", r"amocrm"], "Чтение чертежей": [r"чертеж", r"чертёж"],
}

_COMPILED = {name: [re.compile(p, re.IGNORECASE) for p in pats] for name, pats in SKILLS.items()}
_TAGS = re.compile(r"<[^>]+>")


def clean_html(text: str) -> str:
    return re.sub(r"\s+", " ", _TAGS.sub(" ", text or "")).strip()


def extract_skills(text: str):
    text = clean_html(text)
    if not text:
        return []
    return [name for name, pats in _COMPILED.items() if any(p.search(text) for p in pats)]
