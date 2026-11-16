"""«Работа России» (trudvsem.ru) через открытые данные: http://opendata.trudvsem.ru/api/v1"""
from ..models import Vacancy, experience_from_years
from ..skills import clean_html, extract_skills
from .base import BaseSource

API = "http://opendata.trudvsem.ru/api/v1"

# Коды регионов (первые 2 цифры кода ФНС + 11 нулей)
REGIONS = {
    "москва": "7700000000000", "санкт-петербург": "7800000000000",
    "московская область": "5000000000000", "ленинградская область": "4700000000000",
    "свердловская область": "6600000000000", "новосибирская область": "5400000000000",
    "татарстан": "1600000000000", "краснодарский край": "2300000000000",
    "нижегородская область": "5200000000000", "самарская область": "6300000000000",
    "ростовская область": "6100000000000", "челябинская область": "7400000000000",
    "башкортостан": "0200000000000",
}

# Города hh, которые относятся к региону trudvsem
CITY_TO_REGION = {
    "екатеринбург": "свердловская область", "новосибирск": "новосибирская область",
    "казань": "татарстан", "краснодар": "краснодарский край",
    "нижний новгород": "нижегородская область", "самара": "самарская область",
    "ростов-на-дону": "ростовская область", "челябинск": "челябинская область",
    "уфа": "башкортостан",
}


class TrudvsemSource(BaseSource):
    name = "trudvsem"
    title = "Работа России"
    delay = 0.3

    def search(self, query, limit, region=None):
        region_key = (region or "").lower()
        region_key = CITY_TO_REGION.get(region_key, region_key)
        code = REGIONS.get(region_key)
        url = f"{API}/vacancies/region/{code}" if code else f"{API}/vacancies"
        per_page = min(100, limit)
        self.last_total = 0
        result = []
        page = 0
        while len(result) < limit:
            data = self.get_json(url, params={"text": query, "offset": page, "limit": per_page})
            items = ((data or {}).get("results") or {}).get("vacancies") or []
            if not items:
                break
            for wrap in items:
                vac = wrap.get("vacancy") or {}
                if vac:
                    result.append(self._parse(vac))
            total = int(((data or {}).get("meta") or {}).get("total", 0) or 0)
            self.last_total = total
            page += 1
            if page * per_page >= total or page >= 50:
                break
        return result[:limit]

    def _parse(self, vac):
        req = vac.get("requirement") or {}
        text = " ".join(filter(None, [
            vac.get("duty"), req.get("qualification"), req.get("education"),
            vac.get("skills") if isinstance(vac.get("skills"), str) else None,
        ]))
        text = clean_html(text)
        schedule = vac.get("schedule") or ""
        return Vacancy(
            source=self.name,
            external_id=str(vac.get("id", "")),
            title=vac.get("job-name", ""),
            url=vac.get("vac_url", ""),
            employer=(vac.get("company") or {}).get("name", ""),
            region=(vac.get("region") or {}).get("name", ""),
            salary_from=vac.get("salary_min") or None,
            salary_to=vac.get("salary_max") or None,
            currency="RUR",
            experience=experience_from_years(req.get("experience")),
            employment=vac.get("employment") or "",
            schedule=schedule,
            remote="удал" in schedule.lower(),
            published_at=vac.get("creation-date", ""),
            description=text[:5000],
            skills=extract_skills(text),
        )
