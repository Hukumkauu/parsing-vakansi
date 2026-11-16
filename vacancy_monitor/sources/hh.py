"""HeadHunter (hh.ru) через официальный API: https://api.hh.ru

hh.ru не отдаёт вакансии без ключа приложения (ошибка 403).
Ключ получают бесплатно, зарегистрировав приложение на https://dev.hh.ru/admin
Передать его можно одним из способов (переменные окружения):
  HH_TOKEN                        - готовый токен приложения
  HH_CLIENT_ID и HH_CLIENT_SECRET - программа сама получит токен
"""
import logging
import os

from ..models import Vacancy
from ..skills import clean_html, extract_skills
from .base import BaseSource

log = logging.getLogger(__name__)

API = "https://api.hh.ru"
TOKEN_URL = "https://hh.ru/oauth/token"

NO_ACCESS_MESSAGE = (
    "hh.ru отказал в доступе (код 403): для поиска вакансий нужен ключ приложения. "
    "Зарегистрируйте приложение на https://dev.hh.ru/admin и задайте переменные "
    "HH_CLIENT_ID и HH_CLIENT_SECRET (или HH_TOKEN). Пока hh пропускается."
)

EXPERIENCE = {
    "noExperience": "none",
    "between1And3": "1-3",
    "between3And6": "3-6",
    "moreThan6": "6+",
}

# Популярные регионы hh (id из справочника /areas)
AREAS = {
    "россия": 113, "москва": 1, "санкт-петербург": 2, "екатеринбург": 3,
    "новосибирск": 4, "нижний новгород": 66, "казань": 88, "краснодар": 53,
    "самара": 78, "ростов-на-дону": 76, "челябинск": 104, "уфа": 99,
    "пермь": 72, "воронеж": 26, "красноярск": 54, "омск": 68,
    "московская область": 2019, "ленинградская область": 145,
}


class HHSource(BaseSource):
    name = "hh"
    title = "HeadHunter"
    delay = 0.25
    MAX_RESULTS = 2000  # больше API не отдаёт на один запрос

    def __init__(self, user_agent, details: int = 0):
        super().__init__(user_agent)
        self.session.headers["HH-User-Agent"] = user_agent
        token = os.environ.get("HH_TOKEN") or self._request_token()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        self.details = details  # сколько вакансий догрузить подробно (ключевые навыки)
        self._rates = None
        self.blocked = False  # hh отказал в доступе - больше не обращаемся

    def _request_token(self):
        client_id = os.environ.get("HH_CLIENT_ID")
        client_secret = os.environ.get("HH_CLIENT_SECRET")
        if not (client_id and client_secret):
            return None
        try:
            resp = self.session.post(TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }, timeout=20)
        except Exception as exc:
            log.error("hh: не удалось получить токен: %s", exc)
            return None
        if resp.status_code != 200:
            log.error("hh: токен не выдан (код %d): %s", resp.status_code, resp.text[:200])
            return None
        log.info("hh: токен приложения получен")
        return resp.json().get("access_token")

    def _check_blocked(self):
        if self.last_status == 403 and not self.blocked:
            self.blocked = True
            log.error(NO_ACCESS_MESSAGE)
        return self.blocked
    def currency_rates(self):
        if self._rates is None:
            data = self.get_json(f"{API}/dictionaries") or {}
            self._check_blocked()
            self._rates = {c["code"]: c["rate"] for c in data.get("currency", []) if c.get("rate")}
            if not self._rates:
                self._rates = {"RUR": 1.0}
        return self._rates

    def search(self, query, limit, region=None):
        if self.blocked:
            self.last_total = 0
            return []
        area = AREAS.get((region or "россия").lower(), region or 113)
        per_page = min(100, limit)
        self.last_total = 0
        result = []
        page = 0
        while len(result) < limit and page * per_page < self.MAX_RESULTS:
            params = {
                "text": query,
                "search_field": "name",
                "area": area,
                "per_page": per_page,
                "page": page,
                "order_by": "publication_time",
            }
            data = self.get_json(f"{API}/vacancies", params=params)
            if data is None and self._check_blocked():
                return []
            if not data or not data.get("items"):
                break
            self.last_total = data.get("found", 0)
            for item in data["items"]:
                result.append(self._parse(item))
            page += 1
            if page >= data.get("pages", 0):
                break
        result = result[:limit]
        for vac in result[: self.details]:
            self._load_details(vac)
        return result

    def _parse(self, item):
        salary = item.get("salary") or item.get("salary_range") or {}
        snippet = item.get("snippet") or {}
        schedule = (item.get("schedule") or {}).get("name", "")
        work_format = ", ".join(f.get("name", "") for f in item.get("work_format") or [])
        description = " ".join(filter(None, [snippet.get("requirement"), snippet.get("responsibility")]))
        remote = (item.get("schedule") or {}).get("id") == "remote" or "удал" in work_format.lower()
        return Vacancy(
            source=self.name,
            external_id=str(item["id"]),
            title=item.get("name", ""),
            url=item.get("alternate_url", ""),
            employer=(item.get("employer") or {}).get("name", ""),
            region=(item.get("area") or {}).get("name", ""),
            salary_from=salary.get("from"),
            salary_to=salary.get("to"),
            currency=salary.get("currency") or "RUR",
            salary_gross=salary.get("gross"),
            experience=EXPERIENCE.get((item.get("experience") or {}).get("id"), "unknown"),
            employment=(item.get("employment") or {}).get("name", ""),
            schedule=work_format or schedule,
            remote=remote,
            published_at=item.get("published_at", ""),
            description=clean_html(description),
            skills=extract_skills(description),
        )

    def _load_details(self, vac):
        data = self.get_json(f"{API}/vacancies/{vac.external_id}")
        if not data:
            return
        key_skills = [s["name"] for s in data.get("key_skills", []) if s.get("name")]
        text = clean_html(data.get("description", ""))
        vac.description = text[:5000]
        merged = list(dict.fromkeys(key_skills + extract_skills(text) + vac.skills))
        vac.skills = merged
