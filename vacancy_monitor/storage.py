"""История замеров в SQLite: нужна для динамики на дашборде."""
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    sources TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
    run_id INTEGER NOT NULL,
    position TEXT NOT NULL,
    location TEXT NOT NULL,
    count INTEGER,
    median REAL,
    p25 REAL,
    p75 REAL,
    PRIMARY KEY (run_id, position, location)
);
"""


class Storage:
    def __init__(self, path="data/history.db"):
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def save_run(self, date, sources, stats):
        """Сохраняет замер. Повторный запуск в тот же день заменяет прошлый."""
        day = date.strftime("%Y-%m-%d")
        old = self.conn.execute("SELECT id FROM runs WHERE date = ?", (day,)).fetchall()
        for row in old:
            self.conn.execute("DELETE FROM snapshots WHERE run_id = ?", (row["id"],))
            self.conn.execute("DELETE FROM runs WHERE id = ?", (row["id"],))
        cur = self.conn.execute("INSERT INTO runs (date, sources) VALUES (?, ?)", (day, ",".join(sources)))
        self.conn.executemany(
            "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(cur.lastrowid, s["position"], s["location"], s["count"], s["median"], s["p25"], s["p75"])
             for s in stats],
        )
        self.conn.commit()

    def history(self):
        rows = self.conn.execute(
            """SELECT r.date, s.position, s.location, s.median
               FROM snapshots s JOIN runs r ON r.id = s.run_id ORDER BY r.date"""
        ).fetchall()
        return [dict(r) for r in rows]
