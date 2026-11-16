"""Хранение вакансий и замеров рынка в SQLite."""
import json
import os
import sqlite3
from datetime import datetime

from . import filters

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    region TEXT,
    sources TEXT
);
CREATE TABLE IF NOT EXISTS vacancies (
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    profession TEXT NOT NULL,
    sphere TEXT,
    title TEXT,
    url TEXT,
    employer TEXT,
    region TEXT,
    salary_from REAL,
    salary_to REAL,
    currency TEXT,
    salary_rub REAL,
    experience TEXT,
    employment TEXT,
    schedule TEXT,
    remote INTEGER,
    published_at TEXT,
    description TEXT,
    skills TEXT,
    first_seen_run INTEGER,
    last_seen_run INTEGER,
    PRIMARY KEY (source, external_id, profession)
);
CREATE TABLE IF NOT EXISTS market_totals (
    run_id INTEGER NOT NULL,
    profession TEXT NOT NULL,
    source TEXT NOT NULL,
    found INTEGER,
    collected INTEGER,
    PRIMARY KEY (run_id, profession, source)
);
CREATE TABLE IF NOT EXISTS snapshots (
    run_id INTEGER NOT NULL,
    profession TEXT NOT NULL,
    sphere TEXT,
    found INTEGER,
    collected INTEGER,
    salary_median REAL,
    junior_share REAL,
    remote_share REAL,
    PRIMARY KEY (run_id, profession)
);
CREATE INDEX IF NOT EXISTS idx_vac_last_run ON vacancies(last_seen_run);
"""


class Storage:
    def __init__(self, path="data/vacancies.db"):
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.excluded_count = 0
        self.duplicate_count = 0

    def start_run(self, region, sources):
        cur = self.conn.execute(
            "INSERT INTO runs (started_at, region, sources) VALUES (?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), region, ",".join(sources)),
        )
        self.conn.commit()
        return cur.lastrowid

    def save_vacancies(self, run_id, vacancies, sphere, rates):
        rows = []
        for v in vacancies:
            rows.append((
                v.source, v.external_id, v.profession, sphere, v.title, v.url, v.employer,
                v.region, v.salary_from, v.salary_to, v.currency, v.salary_rub(rates),
                v.experience, v.employment, v.schedule, int(v.remote), v.published_at,
                v.description, json.dumps(v.skills, ensure_ascii=False), run_id, run_id,
            ))
        self.conn.executemany(
            """INSERT INTO vacancies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source, external_id, profession) DO UPDATE SET
                 title=excluded.title, url=excluded.url, employer=excluded.employer,
                 region=excluded.region, salary_from=excluded.salary_from,
                 salary_to=excluded.salary_to, currency=excluded.currency,
                 salary_rub=excluded.salary_rub, experience=excluded.experience,
                 employment=excluded.employment, schedule=excluded.schedule,
                 remote=excluded.remote, published_at=excluded.published_at,
                 description=excluded.description, skills=excluded.skills,
                 sphere=excluded.sphere, last_seen_run=excluded.last_seen_run""",
            rows,
        )
        self.conn.commit()

    def update_run_sources(self, run_id, sources):
        self.conn.execute("UPDATE runs SET sources = ? WHERE id = ?", (",".join(sources), run_id))
        self.conn.commit()

    def save_total(self, run_id, profession, source, found, collected):
        self.conn.execute(
            "INSERT OR REPLACE INTO market_totals VALUES (?, ?, ?, ?, ?)",
            (run_id, profession, source, found, collected),
        )
        self.conn.commit()

    def save_snapshot(self, run_id, stats):
        self.conn.execute(
            "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, stats["profession"], stats["sphere"], stats["found"], stats["count"],
             stats["salary"]["median"], stats["junior_share"], stats["remote_share"]),
        )
        self.conn.commit()

    def last_run(self):
        return self.conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()

    def runs(self):
        return self.conn.execute("SELECT * FROM runs ORDER BY id").fetchall()

    def vacancies_for_run(self, run_id, with_excluded=False):
        """Вакансии замера. По умолчанию без набора на военную службу (см. filters)."""
        rows = self.conn.execute("SELECT * FROM vacancies WHERE last_seen_run = ?", (run_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["skills"] = json.loads(d["skills"] or "[]")
            result.append(d)
        if with_excluded:
            return result
        kept, self.excluded_count, self.duplicate_count = filters.apply(result)
        return kept

    def totals_for_run(self, run_id):
        rows = self.conn.execute(
            "SELECT profession, SUM(found) AS found FROM market_totals WHERE run_id = ? GROUP BY profession",
            (run_id,),
        ).fetchall()
        return {r["profession"]: r["found"] or 0 for r in rows}

    def history(self):
        """Все замеры: {профессия: [(дата, найдено, медиана, доля без опыта), ...]}"""
        rows = self.conn.execute(
            """SELECT s.*, r.started_at FROM snapshots s JOIN runs r ON r.id = s.run_id
               ORDER BY s.run_id"""
        ).fetchall()
        result = {}
        for r in rows:
            result.setdefault(r["profession"], []).append(dict(r))
        return result
