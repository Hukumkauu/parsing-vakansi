"""Расчёт показателей рынка труда по профессиям."""
from collections import Counter
from statistics import median

from .models import EXPERIENCE_LEVELS

# Отсекаем явные ошибки в зарплатах (например, 1 рубль или 100 млн)
SALARY_MIN, SALARY_MAX = 10_000, 2_000_000


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * p
    low = int(k)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (k - low)


def salary_stats(values):
    values = [v for v in values if v and SALARY_MIN <= v <= SALARY_MAX]
    return {
        "count": len(values),
        "median": median(values) if values else None,
        "p25": percentile(values, 0.25),
        "p75": percentile(values, 0.75),
    }


def profession_stats(name, sphere, vacancies, found=0):
    count = len(vacancies)
    salaries = [v["salary_rub"] for v in vacancies]
    exp_counter = Counter(v["experience"] for v in vacancies)
    by_exp = {}
    for level in EXPERIENCE_LEVELS:
        level_vac = [v["salary_rub"] for v in vacancies if v["experience"] == level]
        by_exp[level] = {"count": exp_counter.get(level, 0), "salary": salary_stats(level_vac)}

    skills = Counter()
    for v in vacancies:
        skills.update(set(v["skills"]))

    juniors = [v for v in vacancies if v["experience"] == "none"]
    juniors.sort(key=lambda v: v["salary_rub"] or 0, reverse=True)

    def share(n):
        return round(n / count, 3) if count else 0.0

    return {
        "profession": name,
        "sphere": sphere,
        "count": count,
        "found": found or count,
        "salary": salary_stats(salaries),
        "salary_specified_share": share(sum(1 for s in salaries if s)),
        "by_experience": by_exp,
        "junior_share": share(exp_counter.get("none", 0)),
        "junior_salary": by_exp["none"]["salary"]["median"],
        "remote_share": share(sum(1 for v in vacancies if v["remote"])),
        "top_skills": [(s, n, share(n)) for s, n in skills.most_common(15)],
        "top_regions": Counter(v["region"] for v in vacancies if v["region"]).most_common(7),
        "top_employers": Counter(v["employer"] for v in vacancies if v["employer"]).most_common(7),
        "sources": Counter(v["source"] for v in vacancies),
        "junior_examples": juniors[:5],
    }


def market_stats(vacancies, professions, totals=None):
    totals = totals or {}
    grouped = {}
    for v in vacancies:
        grouped.setdefault(v["profession"], []).append(v)
    result = []
    for p in professions:
        items = grouped.get(p["name"], [])
        if not items and not totals.get(p["name"]):
            continue
        result.append(profession_stats(p["name"], p["sphere"], items, totals.get(p["name"], 0)))
    # Профессии, которых нет в текущем каталоге, но они есть в базе
    known = {p["name"] for p in professions}
    for name, items in grouped.items():
        if name not in known:
            result.append(profession_stats(name, items[0].get("sphere") or "Другое", items, totals.get(name, 0)))
    return result


def sphere_stats(stats):
    spheres = {}
    for s in stats:
        spheres.setdefault(s["sphere"], []).append(s)
    result = []
    for sphere, items in spheres.items():
        medians = [i["salary"]["median"] for i in items if i["salary"]["median"]]
        count = sum(i["count"] for i in items)
        juniors = sum(i["by_experience"]["none"]["count"] for i in items)
        result.append({
            "sphere": sphere,
            "professions": len(items),
            "found": sum(i["found"] for i in items),
            "salary_median": median(medians) if medians else None,
            "junior_share": round(juniors / count, 3) if count else 0.0,
        })
    result.sort(key=lambda x: x["found"], reverse=True)
    return result


def start_score(s):
    """Оценка «насколько легко начать карьеру»: много вакансий для новичков
    и нормальная зарплата на старте. Шкала 0..100."""
    if not s["count"]:
        return 0
    junior = s["by_experience"]["none"]["count"]
    junior_share = s["junior_share"]
    salary = s["junior_salary"] or 0
    demand = min(junior / 50, 1.0)          # абсолютное число вакансий без опыта
    pay = min(salary / 100_000, 1.0)         # зарплата новичка относительно 100 тыс.
    return round(100 * (0.45 * junior_share + 0.30 * demand + 0.25 * pay))


def trend(history_rows):
    """Изменение по сравнению с прошлым замером."""
    if len(history_rows) < 2:
        return None
    prev, cur = history_rows[-2], history_rows[-1]

    def diff(key):
        a, b = prev.get(key), cur.get(key)
        if not a or b is None:
            return None
        return round((b - a) / a * 100, 1)

    return {"found": diff("found"), "salary": diff("salary_median"), "since": prev["started_at"]}
