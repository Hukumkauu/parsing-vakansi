import logging
import time

import requests

log = logging.getLogger(__name__)


class BaseSource:
    """Общая часть для всех сайтов: HTTP-запросы с повторами и паузами."""

    name = "base"
    title = "Базовый источник"
    delay = 0.3  # пауза между запросами, чтобы не получить бан
    last_total = 0  # сколько всего вакансий нашёл сайт по последнему запросу
    last_status = 0  # код ответа последнего запроса

    def __init__(self, user_agent: str = "VacancyMonitor/1.0"):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self._last_request = 0.0

    def get_json(self, url, params=None, headers=None, retries=4):
        for attempt in range(1, retries + 1):
            wait = self.delay - (time.time() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.time()
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=20)
            except requests.RequestException as exc:
                log.warning("%s: ошибка сети (%s), попытка %d", self.name, exc, attempt)
                time.sleep(2 * attempt)
                continue
            self.last_status = resp.status_code
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                log.warning("%s: код %d, повтор через %d c", self.name, resp.status_code, 3 * attempt)
                time.sleep(3 * attempt)
                continue
            if resp.status_code != 403:
                log.error("%s: код %d для %s: %s", self.name, resp.status_code, resp.url, resp.text[:200])
            return None
        return None

    def is_available(self) -> bool:
        return True

    def search(self, query: str, limit: int, region=None):
        """Возвращает список Vacancy. Переопределяется в наследниках."""
        raise NotImplementedError

    def currency_rates(self) -> dict:
        return {}
