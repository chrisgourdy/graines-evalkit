"""Self-contained HTML pages (campaign report, dashboard) rendered from stored data only.

No JavaScript library, no network: charts are inline SVG (`reporting.svg`). Every number on a
page is read from the repository; nothing is produced by an LLM.
"""

from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path

from jinja2 import Environment, select_autoescape
from markupsafe import Markup

from evalkit import __version__
from evalkit.contracts import Campaign, Scorecard
from evalkit.reporting.basic import build_report
from evalkit.reporting.svg import STATUS_COLOR, Bar, bar_chart, histogram, line_chart, stacked_bars
from evalkit.scoring import build_scorecard
from evalkit.storage.sqlite import SQLiteRepository
from evalkit.token_meter import SQLiteTokenMeter

_CSS = """
:root{--ink:#1f2933;--muted:#7b8794;--line:#e4e7eb;--bg:#ffffff;--card:#f7f9fb;--ok:#2f855a;--warn:#b7791f;--fail:#c53030}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
main{max-width:1080px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
nav a{margin-right:14px;color:#3b6ea5;text-decoration:none}nav{margin-bottom:18px;font-size:13px}
.meta{color:var(--muted);font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:14px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px}.tile .k{color:var(--muted);font-size:12px}.tile .v{font-size:20px;font-weight:600}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;color:#fff;font-size:12px;font-weight:600}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}
.warn{color:var(--warn)}.fail{color:var(--fail)}.ok{color:var(--ok)}ul{margin:6px 0 0 18px}figure{margin:12px 0;overflow-x:auto}figure svg{max-width:100%;height:auto}
footer{margin-top:36px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:10px}
@media (max-width:640px){main{padding:16px 12px}h1{font-size:19px}}
"""

_LAYOUT = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }}</title><style>{{ css }}</style></head><body><main>
<nav>{% for href, label in nav %}<a href="{{ href }}">{{ label }}</a>{% endfor %}</nav>
<h1>{{ title }}</h1><div class="meta">{{ subtitle }}</div>
{{ body }}
<footer>EVALKIT {{ version }} · generated {{ generated }} · every value on this page comes from stored records; charts are inline SVG; a simulated adapter is never a production validation.</footer>
</main></body></html>"""

_env = Environment(autoescape=select_autoescape(default=True))
_layout = _env.from_string(_LAYOUT)


def _num(value: float | None, digits: int = 8) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}".rstrip("0").rstrip(".")


def _badge(status: str) -> str:
    return f'<span class="badge" style="background:{STATUS_COLOR.get(status, "#7b8794")}">{escape(status)}</span>'


def _tile(k: str, v: str) -> str:
    return f'<div class="tile"><div class="k">{escape(k)}</div><div class="v">{v}</div></div>'


def _page(title: str, subtitle: str, body: str, nav: list[tuple[str, str]]) -> str:
    from evalkit.contracts import utcnow

    return _layout.render(
        title=title,
        subtitle=subtitle,
        body=Markup(body),  # noqa: S704 — fragments are escaped at construction
        nav=nav,
        css=_CSS,
        version=__version__,
        generated=utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


def _nav(prefix: str = "") -> list[tuple[str, str]]:
    return [
        (f"{prefix}index.html", "Overview"),
        (f"{prefix}finances.html", "Finances"),
        (f"{prefix}improvement.html", "Improvement"),
    ]


# ------------------------------------------------------------------ campaign page
def render_campaign_html(repo: SQLiteRepository, campaign_id: str, *, nav_prefix: str = "") -> str:
    report = build_report(repo, campaign_id)
    card = repo.scorecard_for_campaign(campaign_id) or build_scorecard(
        repo, campaign_id, persist=False
    )
    c = report["campaign"]
    parts: list[str] = []
    parts.append(
        '<div class="grid">'
        + _tile("Overall status", _badge(card.overall_status.value))
        + _tile(
            "Runs (valid / evaluated)",
            f"{report['valid_runs']} / {report['runs_evaluated']} of {report['runs']}",
        )
        + _tile("Eliminatory failures", str(len(card.eliminatory_failures)))
        + _tile(
            "Cost",
            f"{card.cost_status}"
            + (f" · {card.total_cost:.6f} {card.currency}" if card.total_cost is not None else ""),
        )
        + _tile("Usage status", escape(report["usage"]["status"]))
        + _tile(
            "Mean latency",
            f"{card.mean_latency_ms:.1f} ms" if card.mean_latency_ms is not None else "n/a",
        )
        + "</div>"
    )
    if card.eliminatory_failures:
        parts.append(
            "<h2>Eliminatory failures</h2><ul>"
            + "".join(f'<li class="fail">{escape(e)}</li>' for e in card.eliminatory_failures)
            + "</ul>"
        )
    bars = [
        Bar(
            d.dimension.value,
            d.pass_rate,
            d.ci.low if d.ci else None,
            d.ci.high if d.ci else None,
            STATUS_COLOR.get(d.status.value),
            f"n={d.n_evaluated} {d.measurement.value}",
        )
        for d in card.dimensions
    ]
    parts.append(
        "<h2>Dimensions</h2><figure>"
        + bar_chart(
            bars, title="Pass rate per dimension with 95 % interval", max_value=1.0, percent=True
        )
        + "</figure>"
    )
    rows = "".join(
        f"<tr><td>{escape(d.dimension.value)}</td><td>{_badge(d.status.value)}</td><td>{escape(d.measurement.value)}</td>"
        f"<td>{d.n_evaluated}</td><td>{'n/a' if d.pass_rate is None else f'{d.pass_rate:.0%}'}</td>"
        f"<td>{'n/a' if not d.ci else f'[{d.ci.low:.2f}, {d.ci.high:.2f}] {d.ci.method}'}</td><td>{d.critical_failures}</td><td>{escape(d.note or '')}</td></tr>"
        for d in card.dimensions
    )
    parts.append(
        "<table><tr><th>dimension</th><th>status</th><th>measurement</th><th>n</th><th>pass rate</th><th>95 % CI</th><th>critical failures</th><th>note</th></tr>"
        + rows
        + "</table>"
    )
    if card.aggregate_score is not None:
        parts.append(
            f"<p><strong>Aggregate score: {card.aggregate_score:.3f}</strong><br><span class='meta'>{escape(card.aggregate_formula or '')}</span></p>"
        )
    if card.missing_dimensions:
        parts.append(
            "<p class='warn'>Not evaluated: "
            + escape(", ".join(d.value for d in card.missing_dimensions))
            + "</p>"
        )
    sbars = []
    for sid, s in report["scenarios"].items():
        n = sum(v["n"] for v in s["verifications"].values())
        p = sum(v["pass"] for v in s["verifications"].values())
        sbars.append(
            Bar(
                sid,
                (p / n) if n else None,
                note=f"{p}/{n} verifications, {s['attempts']} attempts, {s['errors']} errors",
            )
        )
    parts.append(
        "<h2>Scenarios</h2><figure>"
        + bar_chart(sbars, title="Verification pass rate per scenario", max_value=1.0, percent=True)
        + "</figure>"
    )
    srows = "".join(
        f"<tr><td>{escape(sid)} v{escape(s['version'])}</td><td>{s['attempts']}</td><td>{s['errors']}</td><td>{escape(k)}</td><td>{v['n']}</td><td>{v['pass']}</td><td>{v['fail']}</td><td>{'yes' if v['blocking'] else ''}</td></tr>"
        for sid, s in report["scenarios"].items()
        for k, v in s["verifications"].items()
    )
    parts.append(
        "<table><tr><th>scenario</th><th>attempts</th><th>errors</th><th>verification</th><th>n</th><th>pass</th><th>fail</th><th>blocking</th></tr>"
        + srows
        + "</table>"
    )
    lat = [r.latency_ms for r in repo.list_runs(campaign_id) if r.latency_ms is not None]
    parts.append(
        "<h2>Latency</h2><figure>"
        + histogram(lat, title="Run latency distribution", unit=" ms")
        + "</figure>"
    )
    u = report["usage"]
    parts.append(
        "<h2>Usage and cost</h2><figure>"
        + stacked_bars(
            [
                (
                    "this campaign",
                    {k: float(v) for k, v in u["tokens"].items() if k != "billable_total"},
                )
            ],
            [
                "input_tokens",
                "output_tokens",
                "cached_input_tokens",
                "cache_creation_tokens",
                "reasoning_tokens",
            ],
            title=f"Tokens by category (status {u['status']})",
        )
        + "</figure>"
        + f"<p>Cost status <strong>{escape(report['cost']['status'])}</strong>, known amount {report['cost']['known_amount']} {escape(report['cost']['currency'] or '')}; cost per valid run {_num(report['cost']['cost_per_valid_run'])} ({escape(report['cost']['valid_run_definition'])}); evaluator cost {report['cost']['evaluator_cost_known']}; price snapshot {escape(str(report['cost']['price_snapshot_ids'] or 'none'))}.</p>"
    )
    cmp = report.get("comparison")
    if cmp:
        parts.append("<h2>Comparison with baseline</h2>")
        if cmp.get("result"):
            r = cmp["result"]
            parts.append(
                f"<p>Baseline <code>{escape(cmp['baseline_campaign_id'])}</code>: {r['metric']} {r['baseline_estimate']:.3f} → {r['candidate_estimate']:.3f} (diff {r['difference']:+.3f}). "
                f"{_badge(r['conclusion'])} {escape(r['rationale'])}</p>"
            )
            for w in cmp.get("equivalence_checks", []):
                parts.append(f"<p class='warn'>Non-equivalence: {escape(w)}</p>")
        else:
            parts.append(f"<p class='warn'>{escape(str(cmp.get('note')))}</p>")
    if card.regressions:
        parts.append(
            "<h2>Regressions</h2><ul>"
            + "".join(f"<li class='fail'>{escape(r)}</li>" for r in card.regressions)
            + "</ul>"
        )
    parts.append("<h2>Validity warnings</h2>")
    parts.append(
        "<ul>"
        + "".join(f"<li class='warn'>{escape(w)}</li>" for w in card.validity_warnings)
        + "".join(f"<li>{escape(v)}</li>" for v in report["validity"])
        + "</ul>"
    )
    subtitle = f"{c['project_id']} / {c['agent_id']} v{c['agent_version']} · profile {c['profile']} · campaign status {c['status']} · {c['created_at'][:19]}"
    return _page(f"Campaign {campaign_id}", subtitle, "".join(parts), _nav(nav_prefix))


# ------------------------------------------------------------------ dashboard
def _latest_cards(repo: SQLiteRepository, project_id: str) -> dict[str, Scorecard]:
    latest: dict[str, Scorecard] = {}
    for card in repo.list_scorecards(project_id):
        latest[card.agent_id] = card
    return latest


def build_dashboard(repo: SQLiteRepository, project_id: str, out_dir: Path) -> list[Path]:
    """Static pages: index (global), agent-<id>, campaign-<id>, finances, improvement."""
    out_dir.mkdir(parents=True, exist_ok=True)
    campaigns: list[Campaign] = list(repo.list_campaigns(project_id))
    for camp in campaigns:
        if repo.scorecard_for_campaign(camp.campaign_id) is None and camp.status.value not in (
            "DRY_RUN",
            "PLANNED",
        ):
            build_scorecard(repo, camp.campaign_id)
    latest = _latest_cards(repo, project_id)
    written: list[Path] = []

    # --- index
    tiles = "".join(
        _tile(
            f"{aid}",
            _badge(card.overall_status.value)
            + f" <span class='meta'>v{escape(card.agent_version)} · {escape(card.campaign_id[-8:])}</span>",
        )
        for aid, card in sorted(latest.items())
    )
    alerts = [f"{aid}: {w}" for aid, card in latest.items() for w in card.validity_warnings]
    regressions = [f"{aid}: {r}" for aid, card in latest.items() for r in card.regressions]
    recent = "".join(
        f"<tr><td><a href='campaign-{escape(c.campaign_id)}.html'>{escape(c.campaign_id)}</a></td><td><a href='agent-{escape(c.agent_id)}.html'>{escape(c.agent_id)}</a> v{escape(c.agent_version)}</td><td>{escape(c.profile.value)}</td><td>{escape(c.status.value)}</td><td>{c.created_at:%Y-%m-%d %H:%M}</td><td>{_badge(sc.overall_status.value) if (sc := repo.scorecard_for_campaign(c.campaign_id)) else ''}</td></tr>"
        for c in sorted(campaigns, key=lambda x: x.created_at, reverse=True)[:20]
    )
    meter = SQLiteTokenMeter(repo)
    spend = meter.aggregate(project_id=project_id)
    spend_txt = f"{spend['cost']['known_amount']:.6f} {escape(spend['cost']['currency'] or '')} · {escape(spend['cost']['status'])}"
    open_tickets = sum(
        1
        for t in repo.list_tickets(project_id)
        if t.status.value not in ("CLOSED", "REJECTED", "DUPLICATE")
    )
    body = (
        f"<div class='grid'>{tiles}</div>"
        f"<div class='grid'>{_tile('Campaigns', str(len(campaigns)))}{_tile('Spend (known)', spend_txt)}{_tile('Open tickets', str(open_tickets))}</div>"
        "<h2>Regressions</h2>"
        + (
            "<ul>" + "".join(f"<li class='fail'>{escape(r)}</li>" for r in regressions) + "</ul>"
            if regressions
            else "<p>None detected in latest scorecards.</p>"
        )
        + "<h2>Alerts (validity warnings of latest scorecards)</h2>"
        + (
            "<ul>" + "".join(f"<li class='warn'>{escape(a)}</li>" for a in alerts) + "</ul>"
            if alerts
            else "<p>None.</p>"
        )
        + "<h2>Recent campaigns</h2><table><tr><th>campaign</th><th>agent</th><th>profile</th><th>status</th><th>created</th><th>scorecard</th></tr>"
        + recent
        + "</table>"
    )
    written.append(
        _write(
            out_dir / "index.html",
            _page(f"EVALKIT — {project_id}", "Quality overview", body, _nav()),
        )
    )

    # --- agent pages
    for aid in sorted({c.agent_id for c in campaigns}):
        cards = list(repo.list_scorecards(project_id, aid))
        labels = [f"{c.agent_version}@{c.campaign_id[-6:]}" for c in cards]
        dims = sorted({d.dimension.value for c in cards for d in c.dimensions})
        series = [
            (
                dim,
                [
                    next((d.pass_rate for d in c.dimensions if d.dimension.value == dim), None)
                    for c in cards
                ],
            )
            for dim in dims
        ]
        costs = [
            Bar(lab, c.total_cost if c.total_cost is not None else None, note=c.cost_status or "")
            for lab, c in zip(labels, cards, strict=True)
        ]
        card = latest.get(aid)
        head = (
            "<div class='grid'>"
            + _tile("Latest status", _badge(card.overall_status.value) if card else "n/a")
            + _tile("Version", escape(card.agent_version) if card else "n/a")
            + _tile("Campaigns", str(len(cards)))
            + _tile(
                "Latest cost",
                f"{card.total_cost:.6f} {card.currency}"
                if card and card.total_cost is not None
                else ((card.cost_status or "n/a") if card else "n/a"),
            )
            + "</div>"
        )
        dim_bars = [
            Bar(
                d.dimension.value,
                d.pass_rate,
                d.ci.low if d.ci else None,
                d.ci.high if d.ci else None,
                STATUS_COLOR.get(d.status.value),
                f"n={d.n_evaluated}",
            )
            for d in (card.dimensions if card else [])
        ]
        hist = "".join(
            f"<tr><td><a href='campaign-{escape(c.campaign_id)}.html'>{escape(c.campaign_id)}</a></td><td>{escape(c.agent_version)}</td><td>{_badge(c.overall_status.value)}</td><td>{c.generated_at:%Y-%m-%d %H:%M}</td><td>{len(c.regressions)}</td><td>{len(c.validity_warnings)}</td></tr>"
            for c in reversed(cards)
        )
        body = (
            head
            + "<h2>Latest scorecard</h2><figure>"
            + bar_chart(
                dim_bars,
                title="Pass rate per dimension (latest campaign)",
                max_value=1.0,
                percent=True,
            )
            + "</figure>"
            + "<h2>Trend</h2><figure>"
            + line_chart(
                series,
                labels,
                title="Pass rate per dimension across campaigns",
                percent=True,
                ymax=1.0,
            )
            + "</figure>"
            + "<figure>"
            + bar_chart(
                costs, title="Known cost per campaign", unit=" " + (card.currency if card else "")
            )
            + "</figure>"
            + "<h2>History</h2><table><tr><th>campaign</th><th>version</th><th>status</th><th>scored</th><th>regressions</th><th>warnings</th></tr>"
            + hist
            + "</table>"
        )
        written.append(
            _write(
                out_dir / f"agent-{aid}.html",
                _page(f"Agent {aid}", f"project {project_id}", body, _nav()),
            )
        )

    # --- campaign pages
    for camp in campaigns:
        if camp.status.value in ("DRY_RUN", "PLANNED"):
            continue
        written.append(
            _write(
                out_dir / f"campaign-{camp.campaign_id}.html",
                render_campaign_html(repo, camp.campaign_id),
            )
        )

    # --- finances
    per_campaign: list[tuple[str, dict[str, float]]] = []
    cost_bars: list[Bar] = []
    for camp in campaigns:
        agg = meter.aggregate(campaign_id=camp.campaign_id)
        if agg["records"]["total"] == 0:
            continue
        per_campaign.append(
            (
                f"{camp.agent_id} {camp.campaign_id[-6:]}",
                {k: float(v) for k, v in agg["tokens"].items() if k != "billable_total"},
            )
        )
        cost_bars.append(
            Bar(
                f"{camp.agent_id} {camp.campaign_id[-6:]}",
                agg["cost"]["known_amount"]
                if agg["cost"]["status"] not in ("UNKNOWN", "NO_DATA")
                else None,
                note=agg["cost"]["status"],
            )
        )
    by_model: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in repo._conn.execute(
        "SELECT provider, model, COALESCE(SUM(billable_total),0) AS t, COALESCE(SUM(CAST(cost_amount AS REAL)),0) AS c,"
        " SUM(CASE WHEN source='UNKNOWN' THEN 1 ELSE 0 END) AS unk FROM usage_records WHERE project_id=? GROUP BY provider, model",
        (project_id,),
    ):
        by_model[f"{row['provider']}/{row['model']}"]["tokens"] = float(row["t"])
        by_model[f"{row['provider']}/{row['model']}"]["cost"] = float(row["c"])
        by_model[f"{row['provider']}/{row['model']}"]["unknown"] = float(row["unk"])
    eval_cost = repo._conn.execute(
        "SELECT COALESCE(SUM(CAST(cost_amount AS REAL)),0) AS c, COUNT(*) AS n FROM usage_records WHERE project_id=? AND evaluator_id IS NOT NULL",
        (project_id,),
    ).fetchone()
    model_rows = "".join(
        f"<tr><td>{escape(k)}</td><td>{v['tokens']:.0f}</td><td>{v['cost']:.6f}</td><td>{int(v['unknown'])}</td></tr>"
        for k, v in sorted(by_model.items())
    )
    eval_txt = f"{float(eval_cost['c']):.6f} over {int(eval_cost['n'])} records"
    spend_amount = f"{spend['cost']['known_amount']:.6f} {escape(spend['cost']['currency'] or '')}"
    body = (
        f"<div class='grid'>{_tile('Project spend (known)', spend_amount)}{_tile('Cost status', escape(spend['cost']['status']))}{_tile('Usage status', escape(spend['status']))}{_tile('Evaluator cost', eval_txt)}</div>"
        "<h2>Tokens per campaign</h2><figure>"
        + stacked_bars(
            per_campaign,
            [
                "input_tokens",
                "output_tokens",
                "cached_input_tokens",
                "cache_creation_tokens",
                "reasoning_tokens",
            ],
            title="Tokens by category and campaign (known part)",
        )
        + "</figure>"
        "<h2>Cost per campaign</h2><figure>"
        + bar_chart(
            cost_bars, title="Known cost per campaign", unit=" " + (spend["cost"]["currency"] or "")
        )
        + "</figure>"
        "<h2>By provider and model</h2><table><tr><th>provider/model</th><th>billable tokens</th><th>known cost</th><th>unknown records</th></tr>"
        + model_rows
        + "</table>"
        "<p class='meta'>UNKNOWN records are counted, never summed. Forecast overruns: reserved vs observed per budget via <code>evalkit budget status</code>.</p>"
    )
    written.append(
        _write(
            out_dir / "finances.html",
            _page(f"Finances — {project_id}", "Usage and cost from TOKEN_METER", body, _nav()),
        )
    )

    # --- improvement
    tickets = list(repo.list_tickets(project_id))
    trows = "".join(
        f"<tr><td>{escape(t.ticket_id)}</td><td>{escape(t.title)}</td><td>{escape(t.agent_id)} v{escape(t.agent_version)}</td><td>{escape(t.severity.value)}</td><td>{t.priority}</td><td>{escape(t.status.value)}</td><td>{t.updated_at:%Y-%m-%d}</td></tr>"
        for t in tickets
    )
    body = (
        f"<div class='grid'>{_tile('Tickets', str(len(tickets)))}{_tile('Regressions (latest scorecards)', str(len(regressions)))}</div>"
        "<h2>Backlog</h2>"
        + (
            "<table><tr><th>id</th><th>title</th><th>agent</th><th>severity</th><th>priority</th><th>status</th><th>updated</th></tr>"
            + trows
            + "</table>"
            if tickets
            else "<p>No ticket stored yet (ticket runtime arrives in Phase 6).</p>"
        )
        + "<h2>Regressions</h2>"
        + (
            "<ul>" + "".join(f"<li class='fail'>{escape(r)}</li>" for r in regressions) + "</ul>"
            if regressions
            else "<p>None.</p>"
        )
    )
    written.append(
        _write(
            out_dir / "improvement.html",
            _page(f"Improvement — {project_id}", "Backlog, incidents, regressions", body, _nav()),
        )
    )
    return written


def _write(path: Path, html: str) -> Path:
    path.write_text(html, encoding="utf-8")
    return path


def write_campaign_html(repo: SQLiteRepository, campaign_id: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return _write(out_dir / f"{campaign_id}.html", render_campaign_html(repo, campaign_id))
