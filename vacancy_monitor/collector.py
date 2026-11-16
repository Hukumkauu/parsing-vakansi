"""Сбор вакансий со всех сайтов по каталогу профессий."""
import logging

from .analytics import profession_stats
from .sources import HHSource

log = logging.getLogger(__name__)

# Запасные курсы (сколько единиц валюты за 1 рубль), если hh недоступен
FALLBACK_RATES = {"RUR": 1.0, "RUB": 1.0, "USD": 0.0125, "EUR": 0.0108, "KZT": 6.2, "BYR": 0.037, "UZS": 155.0}


def collect(storage, sources, professions, region, limit):
    sources = [s for s in sources if s.is_available()]
    if not sources:
        raise RuntimeError("Нет доступных источников")
    rates = dict(FALLBACK_RATES)
    for s in sources:
        if isinstance(s, HHSource):
            rates.update(s.currency_rates())
    run_id = storage.start_run(region, [s.name for s in sources])
    log.info("Замер №%d, регион: %s, источники: %s", run_id, region, ", ".join(s.title for s in sources))

    worked = set()  # сайты, которые реально прислали вакансии
    for i, prof in enumerate(professions, 1):
        all_vac = []
        found_total = 0
        for src in sources:
            try:
                items = src.search(prof["query"], limit, region)
            except Exception as exc:  # один сайт упал - продолжаем с другими
                log.error("%s / %s: %s", src.title, prof["name"], exc)
                continue
            for v in items:
                v.profession = prof["name"]
            storage.save_vacancies(run_id, items, prof["sphere"], rates)
            storage.save_total(run_id, prof["name"], src.name, src.last_total, len(items))
            found_total += src.last_total or len(items)
            if items:
                worked.add(src.name)
            all_vac.extend(items)
        log.info("[%d/%d] %s: собрано %d, всего на сайтах %d",
                 i, len(professions), prof["name"], len(all_vac), found_total)

    storage.update_run_sources(run_id, [s.name for s in sources if s.name in worked])

    # Снимок показателей для отслеживания динамики
    vacancies = storage.vacancies_for_run(run_id)
    totals = storage.totals_for_run(run_id)
    for prof in professions:
        items = [v for v in vacancies if v["profession"] == prof["name"]]
        stats = profession_stats(prof["name"], prof["sphere"], items, totals.get(prof["name"], 0))
        storage.save_snapshot(run_id, stats)
    return run_id
