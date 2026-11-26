"""Цепочка мониторинга: собрать данные → убрать дубли и ошибки → привести
должности к единому виду → посчитать показатели → сравнить с вилками банка."""
import logging
from dataclasses import asdict
from datetime import date
from statistics import median

from . import filters
from .models import EXPERIENCE_LEVELS
from .normalize import Normalizer, clean
from .sources import HHSource
from .sources.trudvsem import CITY_TO_REGION
from .workbook import compare

log = logging.getLogger(__name__)

SOURCE_TITLES = {"hh": "HeadHunter", "trudvsem": "Работа России", "superjob": "SuperJob"}

# Явные ошибки в зарплатах
SALARY_MIN, SALARY_MAX = 10_000, 2_000_000
# Запасные курсы (сколько единиц валюты за 1 рубль), если hh недоступен
FALLBACK_RATES = {"RUR": 1.0, "RUB": 1.0, "USD": 0.0125, "EUR": 0.0108, "KZT": 6.2}

ALL_RUSSIA = {"", "россия", "вся россия", "рф"}


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * p
    low = int(k)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (k - low)


def location_matches(location, region):
    loc = clean(location)
    if loc in ALL_RUSSIA:
        return True
    reg = clean(region)
    keys = [w[:5] for w in loc.split() if len(w) >= 3]
    mapped = CITY_TO_REGION.get(loc)
    if mapped:
        keys.append(clean(mapped).split()[0][:6])
    return any(k in reg for k in keys)


def collect(targets, sources, limit):
    """Шаг 1. Сбор вакансий по каждой должности и локации со всех сайтов."""
    rates = dict(FALLBACK_RATES)
    for src in sources:
        if isinstance(src, HHSource):
            rates.update(src.currency_rates())
    raw, worked = [], set()
    for i, target in enumerate(targets, 1):
        got = 0
        queries = [q.strip() for q in target["query"].split(";") if q.strip()] or [target["position"]]
        for src in sources:
            items = []
            for query in queries:
                try:
                    items += src.search(query, limit, target["location"])
                except Exception as exc:  # один сайт упал - продолжаем с другими
                    log.error("%s / %s: %s", src.title, query, exc)
            for v in items:
                d = asdict(v)
                d["salary_rub"] = v.salary_rub(rates)
                d["target_position"] = target["position"]
                d["target_location"] = target["location"]
                raw.append(d)
            if items:
                worked.add(src.name)
            got += len(items)
        log.info("[%d/%d] %s, %s: собрано %d", i, len(targets), target["position"], target["location"], got)
    return raw, [s.name for s in sources if s.name in worked]


def process(raw, targets, dictionary, our_pay, min_sample):
    """Шаги 2-4. Чистка, нормализация, расчёт показателей, сверка с вилками."""
    normalizer = Normalizer([t["position"] for t in targets], dictionary)
    tracked = {(t["position"], t["location"]) for t in targets}
    dashboard = {(t["position"], t["location"]) for t in targets if t["dashboard"]}
    dropped = {"военная служба": 0, "повтор": 0, "ошибка в зарплате": 0, "выброс": 0, "без зарплаты": 0}
    used, other, seen = [], [], set()

    for v in raw:
        # одна и та же вакансия могла найтись по разным запросам
        key = (v["source"], v["external_id"], v["target_location"])
        if key in seen:
            continue
        seen.add(key)
        if filters.is_excluded(v):
            dropped["военная служба"] += 1
            continue
        position, method, _score = normalizer.normalize(v["title"])
        v["experience"] = EXPERIENCE_LEVELS.get(v["experience"], v["experience"])
        if position is None:
            v["reason"] = method or "не совпало с должностями из настроек"
            other.append(v)
            continue
        if (position, v["target_location"]) not in tracked:
            v["reason"] = f"«{position}» не отслеживается в локации {v['target_location']}"
            other.append(v)
            continue
        if not location_matches(v["target_location"], v["region"]):
            v["reason"] = "другая локация"
            other.append(v)
            continue
        if not v["salary_rub"]:
            dropped["без зарплаты"] += 1
            continue
        if not SALARY_MIN <= v["salary_rub"] <= SALARY_MAX:
            dropped["ошибка в зарплате"] += 1
            continue
        v["position"], v["match"] = position, method
        used.append(v)

    # Повторы одного объявления в разных городах и на разных сайтах
    unique, keys = [], set()
    for v in used:
        k = (v["position"], v["target_location"], clean(v["employer"]), clean(v["title"]),
             v["salary_from"], v["salary_to"])
        if v["employer"] and k in keys:
            dropped["повтор"] += 1
            continue
        keys.add(k)
        unique.append(v)

    groups = {}
    for v in unique:
        groups.setdefault((v["position"], v["target_location"]), []).append(v)

    # Выбросы: зарплаты дальше трёх межквартильных размахов от середины
    used = []
    for items in groups.values():
        values = [v["salary_rub"] for v in items]
        q1, q3 = percentile(values, 0.25), percentile(values, 0.75)
        spread = (q3 - q1) * 3 if len(values) >= 8 else None
        for v in items:
            if spread and not (q1 - spread <= v["salary_rub"] <= q3 + spread):
                dropped["выброс"] += 1
            else:
                used.append(v)

    stats = []
    for target in targets:
        key = (target["position"], target["location"])
        if key in {(s["position"], s["location"]) for s in stats}:
            continue
        items = [v for v in used if (v["position"], v["target_location"]) == key]
        values = [v["salary_rub"] for v in items]
        enough = len(values) >= min_sample
        by_source = {}
        for v in items:
            by_source.setdefault(SOURCE_TITLES.get(v["source"], v["source"]), []).append(v["salary_rub"])
        med = median(values) if enough else None
        pay = our_pay.get((key[0].lower(), key[1].lower()))
        deviation, status = compare(med, pay)
        stats.append({
            "position": key[0], "location": key[1], "count": len(values),
            "median": med,
            "p25": percentile(values, 0.25) if enough else None,
            "p75": percentile(values, 0.75) if enough else None,
            "sources": ", ".join(sorted(by_source)),
            "by_source": "; ".join(f"{name}: {round(median(vals) / 1000)} тыс. ({len(vals)})"
                                   for name, vals in sorted(by_source.items())),
            "our_min": pay.get("min") if pay else None,
            "our_max": pay.get("max") if pay else None,
            "deviation": deviation, "status": status if enough else "мало данных",
            "dashboard": key in dashboard,
        })
    return {
        "stats": stats, "used": used, "other": other,
        "dropped": sum(n for k, n in dropped.items() if k != "без зарплаты"),
        "dropped_detail": dropped,
        "new_synonyms": list(normalizer.new_synonyms.values()),
        "date": date.today(),
    }
