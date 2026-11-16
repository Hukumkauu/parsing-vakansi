"""SuperJob (superjob.ru). Нужен бесплатный ключ: https://api.superjob.ru/register
Ключ передаётся через переменную окружения SUPERJOB_KEY."""
import os
from datetime import datetime, timezone

from ..models import Vacancy
from ..skills import clean_html, extract_skills
from .base import BaseSource

API = "https://api.superjob.ru/2.0"

EXPERIENCE = {1: "none", 2: "1-3", 3: "3-6", 4: "6+"}


class SuperJobSource(BaseSource):
    name = "superjob"
    title = "SuperJob"
    delay = 0.2
    MAX_RESULTS = 500

    def __init__(self, user_agent):
        super().__init__(user_agent)
        self.key = os.environ.get("SUPERJOB_KEY", "")
        if self.key:
            self.session.headers["X-Api-App-Id"] = self.key

    def is_available(self):
        return bool(self.key)

    def search(self, query, limit, region=None):
        per_page = min(100, limit)
        self.last_total = 0
        result = []
        page = 0
        while len(result) < limit and page * per_page < self.MAX_RESULTS:
            params = {"keyword": query, "page": page, "count": per_page}
            if region and region.lower() != "россия":
                params["town"] = region
            data = self.get_json(f"{API}/vacancies/", params=params)
            if not data or not data.get("objects"):
                break
            self.last_total = data.get("total", 0)
            result.extend(self._parse(o) for o in data["objects"])
            page += 1
            if not data.get("more"):
                break
        return result[:limit]

    def _parse(self, obj):
        text = clean_html(" ".join(filter(None, [obj.get("candidat"), obj.get("work")])))
        published = obj.get("date_published")
        if published:
            published = datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
        place = (obj.get("place_of_work") or {}).get("title", "")
        return Vacancy(
            source=self.name,
            external_id=str(obj.get("id")),
            title=obj.get("profession", ""),
            url=obj.get("link", ""),
            employer=obj.get("firm_name", ""),
            region=(obj.get("town") or {}).get("title", ""),
            salary_from=obj.get("payment_from") or None,
            salary_to=obj.get("payment_to") or None,
            currency=(obj.get("currency") or "rub").upper().replace("RUB", "RUR"),
            experience=EXPERIENCE.get((obj.get("experience") or {}).get("id"), "unknown"),
            employment=(obj.get("type_of_work") or {}).get("title", ""),
            schedule=place,
            remote="удал" in place.lower(),
            published_at=published or "",
            description=text[:5000],
            skills=extract_skills(text),
        )
