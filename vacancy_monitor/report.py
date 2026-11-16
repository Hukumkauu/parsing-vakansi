"""HTML-отчёт по рынку труда и выгрузка в CSV."""
import csv
import html
import json
import os
from datetime import datetime

from .analytics import sphere_stats, start_score, trend
from .models import EXPERIENCE_LEVELS

SOURCE_TITLES = {"hh": "HeadHunter", "trudvsem": "Работа России", "superjob": "SuperJob"}


def esc(value):
    return html.escape(str(value if value is not None else ""))


def money(value):
    if not value:
        return "—"
    return f"{round(value / 1000):,}".replace(",", " ") + " тыс. ₽"


def pct(value):
    return f"{round((value or 0) * 100)}%"


def change(value):
    if value is None:
        return '<span class="muted">—</span>'
    cls = "up" if value > 0 else "down" if value < 0 else "muted"
    sign = "+" if value > 0 else ""
    return f'<span class="{cls}">{sign}{value}%</span>'


def bar(value, maximum, label=""):
    width = 0 if not maximum or not value else max(2, round(value / maximum * 100))
    return (f'<div class="bar"><div class="fill" style="width:{width}%"></div>'
            f'<span>{esc(label)}</span></div>')


def sparkline(points, width=160, height=36):
    points = [p for p in points if p is not None]
    if len(points) < 2:
        return ""
    lo, hi = min(points), max(points)
    span = hi - lo or 1
    step = width / (len(points) - 1)
    coords = " ".join(
        f"{round(i * step, 1)},{round(height - 4 - (p - lo) / span * (height - 8), 1)}"
        for i, p in enumerate(points)
    )
    return (f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
            f'<polyline points="{coords}" fill="none" stroke="currentColor" stroke-width="2"/></svg>')


CSS = """
:root{--bg:#f6f7fb;--card:#fff;--text:#1d2433;--muted:#6b7385;--line:#e3e6ee;
--accent:#3b6ef5;--accent-soft:#dfe7fe;--up:#1a8f4c;--down:#c8372d}
@media (prefers-color-scheme:dark){:root{--bg:#12151c;--card:#1b1f29;--text:#e7e9ef;
--muted:#99a0b0;--line:#2c3240;--accent:#7b9dff;--accent-soft:#27324f;--up:#4cc27f;--down:#f0786e}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:28px;margin:0 0 4px}h2{font-size:21px;margin:36px 0 12px}h3{margin:0 0 4px;font-size:18px}
.muted{color:var(--muted)}.up{color:var(--up)}.down{color:var(--down)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-top:20px}
.kpi,.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi b{display:block;font-size:24px}
.table-wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;min-width:760px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-size:13px;color:var(--muted);cursor:pointer;user-select:none;white-space:nowrap;position:sticky;top:0;background:var(--card)}
th:hover{color:var(--text)}td.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:0}
.bar{position:relative;background:var(--accent-soft);border-radius:6px;height:22px;min-width:110px;overflow:hidden}
.bar .fill{position:absolute;inset:0 auto 0 0;background:var(--accent);opacity:.75}
.bar span{position:relative;padding:0 8px;font-size:13px;line-height:22px;white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
.card .row{display:grid;grid-template-columns:140px 1fr;gap:8px;align-items:center;margin:4px 0;font-size:14px}
.card .row>span:first-child{overflow-wrap:anywhere;hyphens:auto}
.tag{display:inline-block;background:var(--accent-soft);border-radius:999px;padding:1px 9px;margin:2px;font-size:13px}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 14px}
.filters button{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:999px;padding:4px 12px;cursor:pointer;font:inherit;font-size:14px}
.filters button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.spark{color:var(--accent);vertical-align:middle}
a{color:var(--accent)}details summary{cursor:pointer;color:var(--muted);margin-top:8px}
ul.list{margin:4px 0;padding-left:18px}
.note{font-size:13px;color:var(--muted);margin-top:6px}
@media (max-width:420px){.cards{grid-template-columns:1fr}.card .row{grid-template-columns:96px 1fr}}
"""

JS = """
document.querySelectorAll('table.sortable').forEach(function(table){
  table.querySelectorAll('th').forEach(function(th, idx){
    th.addEventListener('click', function(){
      var body = table.tBodies[0];
      var rows = Array.from(body.rows);
      var asc = th.dataset.dir !== 'asc';
      table.querySelectorAll('th').forEach(function(h){ delete h.dataset.dir; });
      th.dataset.dir = asc ? 'asc' : 'desc';
      rows.sort(function(a, b){
        var x = a.cells[idx].dataset.v, y = b.cells[idx].dataset.v;
        if (x === undefined) { x = a.cells[idx].innerText; y = b.cells[idx].innerText; }
        var nx = parseFloat(x), ny = parseFloat(y);
        var r = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : String(x).localeCompare(String(y), 'ru');
        return asc ? r : -r;
      });
      rows.forEach(function(r){ body.appendChild(r); });
    });
  });
});
document.querySelectorAll('.filters button').forEach(function(btn){
  btn.addEventListener('click', function(){
    document.querySelectorAll('.filters button').forEach(function(b){ b.classList.remove('on'); });
    btn.classList.add('on');
    var s = btn.dataset.sphere;
    document.querySelectorAll('[data-sphere-row]').forEach(function(el){
      el.style.display = (!s || el.dataset.sphereRow === s) ? '' : 'none';
    });
  });
});
"""


def _summary_table(stats, history):
    rows = []
    for s in stats:
        hist = history.get(s["profession"], [])
        t = trend(hist) or {}
        sal = s["salary"]
        rows.append(f"""<tr data-sphere-row="{esc(s['sphere'])}">
<td><a href="#p-{_anchor(s['profession'])}">{esc(s['profession'])}</a></td>
<td>{esc(s['sphere'])}</td>
<td class="num" data-v="{s['found']}">{_int(s['found'])}</td>
<td class="num" data-v="{sal['median'] or 0}">{money(sal['median'])}</td>
<td class="num" data-v="{sal['p25'] or 0}">{money(sal['p25'])} – {money(sal['p75'])}</td>
<td class="num" data-v="{s['junior_salary'] or 0}">{money(s['junior_salary'])}</td>
<td class="num" data-v="{s['junior_share']}">{pct(s['junior_share'])}</td>
<td class="num" data-v="{s['remote_share']}">{pct(s['remote_share'])}</td>
<td class="num" data-v="{start_score(s)}">{start_score(s)}</td>
<td class="num" data-v="{t.get('found') or 0}">{change(t.get('found'))}</td>
<td class="num" data-v="{t.get('salary') or 0}">{change(t.get('salary'))}</td>
</tr>""")
    return f"""<div class="table-wrap"><table class="sortable">
<thead><tr><th>Профессия</th><th>Сфера</th><th>Вакансий на сайтах</th><th>Медиана зарплаты</th>
<th>Типичный диапазон</th><th>Зарплата без опыта</th><th>Без опыта</th><th>Удалённо</th>
<th title="0–100: насколько легко начать карьеру">Старт ⓘ</th><th>Спрос, изм.</th><th>Зарплата, изм.</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="note">Нажмите на заголовок столбца, чтобы отсортировать. «Типичный диапазон» - половина вакансий
платит в этих пределах. «Старт» учитывает долю и число вакансий без опыта и зарплату новичка.
«Изм.» - изменение по сравнению с прошлым замером.</p>"""


def _anchor(name):
    return "".join(ch if ch.isalnum() else "-" for ch in name.lower())


def _int(n):
    return f"{n:,}".replace(",", " ")


def _sphere_block(stats):
    spheres = sphere_stats(stats)
    max_found = max((s["found"] for s in spheres), default=0)
    max_sal = max((s["salary_median"] or 0 for s in spheres), default=0)
    rows = "".join(f"""<tr><td>{esc(s['sphere'])}</td>
<td>{bar(s['found'], max_found, _int(s['found']))}</td>
<td>{bar(s['salary_median'], max_sal, money(s['salary_median']))}</td>
<td class="num">{pct(s['junior_share'])}</td></tr>""" for s in spheres)
    return f"""<div class="table-wrap"><table><thead><tr><th>Сфера</th><th>Спрос (вакансий)</th>
<th>Медиана зарплаты</th><th>Без опыта</th></tr></thead><tbody>{rows}</tbody></table></div>"""


def _top_block(stats):
    with_salary = [s for s in stats if s["salary"]["median"]]
    by_salary = sorted(with_salary, key=lambda s: s["salary"]["median"], reverse=True)[:7]
    by_demand = sorted(stats, key=lambda s: s["found"], reverse=True)[:7]
    by_start = sorted(stats, key=start_score, reverse=True)[:7]

    def lst(items, fmt):
        return "<ol class='list'>" + "".join(f"<li>{esc(s['profession'])} - {fmt(s)}</li>" for s in items) + "</ol>"

    return f"""<div class="cards">
<div class="card"><h3>💰 Самые высокие зарплаты</h3>{lst(by_salary, lambda s: money(s['salary']['median']))}</div>
<div class="card"><h3>📈 Самый большой спрос</h3>{lst(by_demand, lambda s: _int(s['found']) + ' вакансий')}</div>
<div class="card"><h3>🎓 Легче всего начать без опыта</h3>{lst(by_start, lambda s: f"{pct(s['junior_share'])} вакансий без опыта, {money(s['junior_salary'])}")}</div>
</div>"""


def _profession_card(s, history):
    exp = s["by_experience"]
    max_cnt = max((e["count"] for e in exp.values()), default=0)
    max_sal = max((e["salary"]["median"] or 0 for e in exp.values()), default=0)
    exp_rows = "".join(
        f'<div class="row"><span>{esc(EXPERIENCE_LEVELS[k])}</span>'
        f'{bar(e["salary"]["median"], max_sal, money(e["salary"]["median"]) + f" · {e["count"]} вак.")}</div>'
        for k, e in exp.items() if e["count"] and k != "unknown"
    ) or '<p class="muted">Нет данных</p>'
    max_skill = s["top_skills"][0][1] if s["top_skills"] else 0
    skill_rows = "".join(
        f'<div class="row"><span>{esc(name)}</span>{bar(n, max_skill, pct(share))}</div>'
        for name, n, share in s["top_skills"][:8]
    ) or '<p class="muted">Навыки не найдены</p>'
    regions = "".join(f'<span class="tag">{esc(r)} · {n}</span>' for r, n in s["top_regions"])
    employers = "".join(f'<span class="tag">{esc(r)} · {n}</span>' for r, n in s["top_employers"])
    juniors = "".join(
        f'<li><a href="{esc(v["url"])}" target="_blank" rel="noopener">{esc(v["title"])}</a> - '
        f'{esc(v["employer"])}, {esc(v["region"])}, {money(v["salary_rub"])}</li>'
        for v in s["junior_examples"]
    )
    hist = history.get(s["profession"], [])
    spark_found = sparkline([h["found"] for h in hist])
    spark_sal = sparkline([h["salary_median"] for h in hist])
    dynamics = ""
    if spark_found or spark_sal:
        dynamics = (f'<div class="row"><span>Спрос</span>{spark_found}</div>'
                    f'<div class="row"><span>Зарплата</span>{spark_sal}</div>'
                    f'<p class="note">Замеров: {len(hist)}, первый - {esc(hist[0]["started_at"][:10])}</p>')
    sources = ", ".join(f"{SOURCE_TITLES.get(k, k)}: {n}" for k, n in s["sources"].items())
    return f"""<div class="card" id="p-{_anchor(s['profession'])}" data-sphere-row="{esc(s['sphere'])}">
<h3>{esc(s['profession'])}</h3>
<div class="muted">{esc(s['sphere'])} · вакансий на сайтах: {_int(s['found'])} · проанализировано: {s['count']}</div>
<p>Медиана: <b>{money(s['salary']['median'])}</b> · без опыта: <b>{money(s['junior_salary'])}</b> ·
удалённо: {pct(s['remote_share'])} · старт: <b>{start_score(s)}</b>/100</p>
<h4>Зарплата по опыту</h4>{exp_rows}
<h4>Что требуют работодатели</h4>{skill_rows}
{('<h4>Динамика</h4>' + dynamics) if dynamics else ''}
<details><summary>Регионы и работодатели</summary><p>{regions}</p><p>{employers}</p></details>
{('<details><summary>Вакансии для начинающих</summary><ul class="list">' + juniors + '</ul></details>') if juniors else ''}
<p class="note">Источники: {esc(sources) or '—'} · зарплата указана в {pct(s['salary_specified_share'])} вакансий</p>
</div>"""


def build_html(stats, history, run, output):
    stats = sorted(stats, key=lambda s: s["found"], reverse=True)
    total_found = sum(s["found"] for s in stats)
    total_count = sum(s["count"] for s in stats)
    medians = sorted(s["salary"]["median"] for s in stats if s["salary"]["median"])
    overall = medians[len(medians) // 2] if medians else None
    junior = sum(s["by_experience"]["none"]["count"] for s in stats)
    spheres = sorted({s["sphere"] for s in stats})
    sources = ", ".join(SOURCE_TITLES.get(x, x) for x in (run["sources"] or "").split(",") if x)
    filters = '<button class="on" data-sphere="">Все</button>' + "".join(
        f'<button data-sphere="{esc(sp)}">{esc(sp)}</button>' for sp in spheres)

    page = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Рынок труда - профориентация</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>Мониторинг рынка труда</h1>
<div class="muted">Профориентация для школьников и студентов · регион: {esc((run['region'] or '').title())} ·
замер от {esc(run['started_at'].replace('T', ' '))} · источники: {esc(sources)}</div>
<div class="kpis">
<div class="kpi"><span class="muted">Профессий</span><b>{len(stats)}</b></div>
<div class="kpi"><span class="muted">Вакансий на сайтах</span><b>{_int(total_found)}</b></div>
<div class="kpi"><span class="muted">Проанализировано</span><b>{_int(total_count)}</b></div>
<div class="kpi"><span class="muted">Медиана по профессиям</span><b>{money(overall)}</b></div>
<div class="kpi"><span class="muted">Вакансий без опыта</span><b>{pct(junior / total_count if total_count else 0)}</b></div>
</div>
<h2>Рейтинги</h2>{_top_block(stats)}
<h2>Сферы деятельности</h2>{_sphere_block(stats)}
<h2>Все профессии</h2><div class="filters">{filters}</div>{_summary_table(stats, history)}
<h2>Подробно по профессиям</h2><div class="cards">{''.join(_profession_card(s, history) for s in stats)}</div>
<p class="note">Зарплаты пересчитаны в рубли, указаны «как в вакансии» (часть работодателей пишет до вычета
налога). Явно ошибочные суммы (меньше 10 тыс. и больше 2 млн ₽) не учитываются. Сформировано
{datetime.now().strftime('%d.%m.%Y %H:%M')}.</p>
</div><script>{JS}</script></body></html>"""
    folder = os.path.dirname(output)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(page)
    return output


CSV_FIELDS = ["profession", "sphere", "source", "title", "employer", "region", "salary_from",
              "salary_to", "currency", "salary_rub", "experience", "employment", "schedule",
              "remote", "published_at", "skills", "url"]


def export_csv(vacancies, output):
    folder = os.path.dirname(output)
    if folder:
        os.makedirs(folder, exist_ok=True)
    # utf-8-sig, чтобы Excel правильно открыл русские буквы
    with open(output, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for v in vacancies:
            row = dict(v)
            row["skills"] = ", ".join(v["skills"])
            row["experience"] = EXPERIENCE_LEVELS.get(v["experience"], v["experience"])
            writer.writerow(row)
    return output


def export_json(stats, output):
    data = []
    for s in stats:
        item = {k: v for k, v in s.items() if k != "junior_examples"}
        item["sources"] = dict(s["sources"])
        item["start_score"] = start_score(s)
        data.append(item)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return output
