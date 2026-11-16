from dataclasses import dataclass, field
from typing import List, Optional


# Единая шкала опыта для всех сайтов
EXPERIENCE_LEVELS = {
    "none": "Без опыта",
    "1-3": "От 1 до 3 лет",
    "3-6": "От 3 до 6 лет",
    "6+": "Более 6 лет",
    "unknown": "Не указан",
}


@dataclass
class Vacancy:
    source: str
    external_id: str
    title: str
    url: str = ""
    employer: str = ""
    region: str = ""
    salary_from: Optional[float] = None
    salary_to: Optional[float] = None
    currency: str = "RUR"
    salary_gross: Optional[bool] = None
    experience: str = "unknown"
    employment: str = ""
    schedule: str = ""
    remote: bool = False
    published_at: str = ""
    description: str = ""
    skills: List[str] = field(default_factory=list)
    profession: str = ""

    def salary_rub(self, rates: dict) -> Optional[float]:
        """Средняя зарплата вакансии в рублях или None."""
        low, high = self.salary_from, self.salary_to
        if low and high:
            value = (low + high) / 2
        else:
            value = low or high
        if not value:
            return None
        rate = rates.get(self.currency.upper(), 1.0) if self.currency else 1.0
        if not rate:
            return None
        return value / rate


def experience_from_years(years) -> str:
    try:
        years = float(years)
    except (TypeError, ValueError):
        return "unknown"
    if years < 1:
        return "none"
    if years < 3:
        return "1-3"
    if years < 6:
        return "3-6"
    return "6+"
