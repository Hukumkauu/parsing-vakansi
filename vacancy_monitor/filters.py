"""Отсев вакансий, которые искажают статистику гражданских профессий.

1. Одно и то же объявление, размещённое во многих регионах, считается один раз.
2. Набор на военную службу по контракту публикуется под названиями обычных
профессий («Сварщик», «Водитель») с зарплатами в разы выше рынка, поэтому
такие объявления в расчёт не берутся.
"""
import re

EXCLUDE = re.compile(
    r"военнослужащ|военн\w* служб|\bсво\b|специальн\w* военн\w* операц|"
    r"министерств\w* обороны|минобороны|\bмо рф\b|военн\w* комиссариат|военкомат|"
    r"пункт\w* отбора|рембат|ремонтн\w* батальон|добровольческ\w* (отряд|формирован)|"
    r"зон\w* (сво|боевых действий)|контракт\w* с (мо|министерств)",
    re.IGNORECASE,
)


def is_excluded(vacancy: dict) -> bool:
    text = " ".join(str(vacancy.get(k) or "") for k in ("title", "employer", "description"))
    return bool(EXCLUDE.search(text))


def _norm(value):
    return re.sub(r"\W+", " ", str(value or "").lower()).strip()


def duplicate_key(vacancy: dict):
    return (vacancy.get("profession"), _norm(vacancy.get("employer")), _norm(vacancy.get("title")),
            vacancy.get("salary_from"), vacancy.get("salary_to"))


def apply(vacancies):
    """Возвращает (оставшиеся вакансии, отсеяно военных, отсеяно повторов)."""
    civil = [v for v in vacancies if not is_excluded(v)]
    seen, unique = set(), []
    for v in civil:
        key = duplicate_key(v)
        if not v.get("employer") or key not in seen:
            seen.add(key)
            unique.append(v)
    return unique, len(vacancies) - len(civil), len(civil) - len(unique)
