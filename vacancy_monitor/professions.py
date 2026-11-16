"""Каталог профессий для профориентации.

Каждая профессия: название, сфера, поисковый запрос и слова-исключения
(чтобы, например, «Повар» не находил «Повар-кондитер-технолог-менеджер»).
Свой каталог можно положить в professions.json рядом с main.py.
"""
import json
import os

DEFAULT_PROFESSIONS = [
    # IT
    {"name": "Программист Python", "sphere": "IT", "query": "python разработчик"},
    {"name": "Frontend-разработчик", "sphere": "IT", "query": "frontend разработчик"},
    {"name": "Java-разработчик", "sphere": "IT", "query": "java разработчик"},
    {"name": "Тестировщик (QA)", "sphere": "IT", "query": "тестировщик"},
    {"name": "Аналитик данных", "sphere": "IT", "query": "аналитик данных"},
    {"name": "Системный администратор", "sphere": "IT", "query": "системный администратор"},
    {"name": "DevOps-инженер", "sphere": "IT", "query": "devops"},
    {"name": "Дизайнер интерфейсов", "sphere": "IT", "query": "UX/UI дизайнер"},
    # Информационная безопасность
    {"name": "Специалист по информационной безопасности", "sphere": "Информационная безопасность",
     "query": "специалист по информационной безопасности"},
    {"name": "Пентестер", "sphere": "Информационная безопасность", "query": "пентест"},
    {"name": "Аналитик SOC", "sphere": "Информационная безопасность", "query": "аналитик SOC"},
    # Инженерия и производство
    {"name": "Инженер-конструктор", "sphere": "Инженерия", "query": "инженер-конструктор"},
    {"name": "Инженер-электрик", "sphere": "Инженерия", "query": "инженер-электрик"},
    {"name": "Инженер-строитель", "sphere": "Инженерия", "query": "инженер ПТО"},
    {"name": "Электромонтажник", "sphere": "Рабочие профессии", "query": "электромонтажник"},
    {"name": "Сварщик", "sphere": "Рабочие профессии", "query": "сварщик"},
    {"name": "Оператор станков ЧПУ", "sphere": "Рабочие профессии", "query": "оператор ЧПУ"},
    {"name": "Автомеханик", "sphere": "Рабочие профессии", "query": "автомеханик"},
    # Медицина
    {"name": "Врач-терапевт", "sphere": "Медицина", "query": "врач терапевт"},
    {"name": "Медсестра / медбрат", "sphere": "Медицина", "query": "медицинская сестра"},
    {"name": "Фармацевт", "sphere": "Медицина", "query": "фармацевт"},
    # Образование
    {"name": "Учитель", "sphere": "Образование", "query": "учитель"},
    {"name": "Воспитатель", "sphere": "Образование", "query": "воспитатель"},
    # Экономика и управление
    {"name": "Бухгалтер", "sphere": "Экономика", "query": "бухгалтер"},
    {"name": "Финансовый аналитик", "sphere": "Экономика", "query": "финансовый аналитик"},
    {"name": "Юрист", "sphere": "Экономика", "query": "юрист"},
    {"name": "HR-менеджер", "sphere": "Экономика", "query": "HR менеджер"},
    {"name": "Менеджер по продажам", "sphere": "Торговля", "query": "менеджер по продажам"},
    {"name": "Маркетолог", "sphere": "Маркетинг и медиа", "query": "маркетолог"},
    {"name": "SMM-специалист", "sphere": "Маркетинг и медиа", "query": "SMM"},
    {"name": "Графический дизайнер", "sphere": "Маркетинг и медиа", "query": "графический дизайнер"},
    # Сфера услуг и логистика
    {"name": "Повар", "sphere": "Сфера услуг", "query": "повар"},
    {"name": "Администратор", "sphere": "Сфера услуг", "query": "администратор ресепшн"},
    {"name": "Логист", "sphere": "Логистика", "query": "логист"},
    {"name": "Водитель категории C", "sphere": "Логистика", "query": "водитель категории C"},
]


def load_professions(path: str = "professions.json"):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            item.setdefault("sphere", "Другое")
            item.setdefault("query", item["name"])
        return data
    return DEFAULT_PROFESSIONS


def select_professions(professions, names=None, spheres=None):
    result = professions
    if names:
        low = [n.lower() for n in names]
        result = [p for p in result if any(n in p["name"].lower() for n in low)]
    if spheres:
        low = [s.lower() for s in spheres]
        result = [p for p in result if any(s in p["sphere"].lower() for s in low)]
    return result
