from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from html import escape
from .store import Rule
from .parser import Session

_STYLE = """
*, *::before, *::after { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, sans-serif; max-width: 960px;
       margin: 40px auto; padding: 0 24px; color: #1a1a1a; background: #fff; }
h1 { font-size: 1.5rem; font-weight: 700; margin: 0 0 4px; }
h2 { font-size: 1.1rem; font-weight: 600; margin: 2.5rem 0 0.75rem;
     border-bottom: 2px solid #e8e8e8; padding-bottom: 6px; }
.meta { color: #666; font-size: 0.88rem; margin-bottom: 1.5rem; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr));
                gap: 12px; margin-bottom: 2rem; }
.stat-box { background: #f7f8fa; border: 1px solid #e0e2e6; border-radius: 8px;
            padding: 14px 18px; }
.stat-box .label { font-size: 0.78rem; color: #666; text-transform: uppercase;
                   letter-spacing: .04em; margin-bottom: 4px; }
.stat-box .value { font-size: 1.5rem; font-weight: 700; color: #111; }
table { border-collapse: collapse; width: 100%; font-size: 0.875rem;
        margin-bottom: 1.5rem; }
th { background: #f4f5f7; text-align: left; padding: 9px 12px;
     border: 1px solid #dde1e7; white-space: nowrap; }
td { padding: 8px 12px; border: 1px solid #dde1e7; vertical-align: top; }
tr:nth-child(even) td { background: #fafbfc; }
.rule-card { border: 1px solid #dde1e7; border-radius: 8px; padding: 18px 20px;
             margin-bottom: 18px; }
.rule-card.has-contradiction { border-left: 4px solid #dc2626; }
.rule-card.activated { border-left: 4px solid #16a34a; }
.rule-header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
               margin-bottom: 10px; }
.rule-id { font-weight: 700; font-family: monospace; font-size: 1rem; color: #1a1a1a; }
.badge { display: inline-block; font-size: 0.75rem; padding: 2px 8px;
         border-radius: 12px; font-weight: 600; }
.badge-active { background: #dcfce7; color: #15803d; }
.badge-draft  { background: #f1f5f9; color: #475569; }
.badge-conflict { background: #fee2e2; color: #b91c1c; }
.sig { font-family: monospace; background: #f1f5f9; padding: 2px 7px;
       border-radius: 4px; font-size: 0.85rem; color: #334155; }
.rule-text { margin: 10px 0 6px; line-height: 1.5; }
.scope-row { font-family: monospace; font-size: 0.82rem; color: #475569; }
.stats-row { display: flex; gap: 24px; flex-wrap: wrap; margin: 10px 0 6px;
             font-size: 0.85rem; }
.stats-row .kv { display: flex; flex-direction: column; }
.stats-row .kv .k { font-size: 0.72rem; color: #94a3b8; text-transform: uppercase;
                     letter-spacing: .04em; }
.stats-row .kv .v { font-weight: 600; color: #1e293b; }
.ci-bar-wrap { margin: 6px 0; }
.ci-label { font-size: 0.78rem; color: #666; margin-bottom: 2px; }
.ci-track { background: #e2e8f0; border-radius: 4px; height: 10px;
             position: relative; overflow: visible; }
.ci-fill { background: #3b82f6; border-radius: 4px; height: 10px;
            position: absolute; }
.ci-fill.after { background: #16a34a; }
.ci-point { width: 3px; height: 16px; background: #1e3a5f; position: absolute;
             top: -3px; border-radius: 2px; }
.ci-point.after { background: #14532d; }
.note-box { background: #fffbeb; border: 1px solid #fcd34d; border-radius: 6px;
            padding: 10px 14px; font-size: 0.83rem; color: #78350f;
            margin: 2rem 0 0; }
.warn { color: #d97706; font-weight: 600; }
.good { color: #15803d; font-weight: 600; }
.na   { color: #94a3b8; }
a { color: #2563eb; }
"""


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{100 * n / total:.0f}%"


def _rate_str(r: float) -> str:
    return f"{r:.1%}"


def _ci_bar(before: dict, after: dict | None) -> str:
    """Render an inline before/after CI bar (0-100% track)."""
    b_lo, b_hi = before["ci_95"]
    b_rate = before["rate"]

    def pct(v: float) -> str:
        return f"{min(max(v * 100, 0), 100):.1f}%"

    b_fill = (
        f'<div class="ci-fill" style="left:{pct(b_lo)};width:{pct(b_hi - b_lo)}"></div>'
        f'<div class="ci-point" style="left:{pct(b_rate)}"></div>'
    )
    before_bar = (
        f'<div class="ci-bar-wrap">'
        f'<div class="ci-label">Before (n={before["sessions"]}, '
        f'rate={_rate_str(b_rate)}, CI {_rate_str(b_lo)}-{_rate_str(b_hi)})</div>'
        f'<div class="ci-track">{b_fill}</div>'
        f'</div>'
    )

    after_bar = ""
    if after:
        a_lo, a_hi = after["ci_95"]
        a_rate = after["rate"]
        a_fill = (
            f'<div class="ci-fill after" style="left:{pct(a_lo)};width:{pct(a_hi - a_lo)}"></div>'
            f'<div class="ci-point after" style="left:{pct(a_rate)}"></div>'
        )
        after_bar = (
            f'<div class="ci-bar-wrap">'
            f'<div class="ci-label">After &nbsp;(n={after["sessions"]}, '
            f'rate={_rate_str(a_rate)}, CI {_rate_str(a_lo)}-{_rate_str(a_hi)})</div>'
            f'<div class="ci-track">{a_fill}</div>'
            f'</div>'
        )

    return before_bar + after_bar


def _preview_html(p: dict) -> str:
    fires = p.get("fires_in_sessions", 0)
    total = p.get("total_sessions", 0)
    mistakes = p.get("mistake_in_sessions", 0)
    false_hits = p.get("false_hits", 0)
    precision = (mistakes / fires) if fires else 0
    prec_cls = "good" if precision >= 0.5 else "warn"
    return (
        f'<div class="stats-row">'
        f'<div class="kv"><span class="k">Fires in</span>'
        f'<span class="v">{fires}/{total} sessions</span></div>'
        f'<div class="kv"><span class="k">True hits</span>'
        f'<span class="v">{mistakes}</span></div>'
        f'<div class="kv"><span class="k">False hits</span>'
        f'<span class="v">{false_hits}</span></div>'
        f'<div class="kv"><span class="k">Precision</span>'
        f'<span class="v {prec_cls}">{precision:.0%}</span></div>'
        f'</div>'
    )


def _measure_html(m: dict) -> str:
    if "error" in m:
        return f'<p class="warn">Measure error: {escape(m["error"])}</p>'
    b = m["before"]
    a = m["after"]
    note = m.get("note", "")
    warn = ""
    if m.get("small_sample_warning"):
        warn = '<p class="warn">Small sample warning: &lt;20 sessions after activation.</p>'
    return _ci_bar(b, a) + warn + f'<p style="font-size:.82rem;color:#555">{escape(note)}</p>'


def generate_report(
    sessions: list[Session],
    clusters: list[tuple[str, set]],
    rules: list[Rule],
    rules_file: str | Path,
) -> str:
    rules_path = Path(rules_file)
    report_path = rules_path.parent / "report.html"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n = len(sessions)
    n_activated = sum(1 for r in rules if r.activated_at)
    n_measured = sum(1 for r in rules if r.measure_result and "error" not in r.measure_result)

    # Summary grid
    summary_grid = (
        f'<div class="summary-grid">'
        f'<div class="stat-box"><div class="label">Sessions</div><div class="value">{n}</div></div>'
        f'<div class="stat-box"><div class="label">Clusters found</div><div class="value">{len(clusters)}</div></div>'
        f'<div class="stat-box"><div class="label">Rules drafted</div><div class="value">{len(rules)}</div></div>'
        f'<div class="stat-box"><div class="label">Activated</div><div class="value">{n_activated}</div></div>'
        f'<div class="stat-box"><div class="label">Measured</div><div class="value">{n_measured}</div></div>'
        f'</div>'
    )

    # Top clusters table
    rows = []
    for sig, session_ids in clusters:
        rule = next((r for r in rules if r.signature == sig), None)
        rule_text = escape(rule.rule_text) if rule else "<span class='na'>no rule</span>"
        rule_id = rule.rule_id if rule else "-"
        rows.append(
            f"<tr><td><code>{escape(rule_id)}</code></td>"
            f"<td><span class='sig'>{escape(sig)}</span></td>"
            f"<td>{len(session_ids)}</td>"
            f"<td>{rule_text}</td></tr>"
        )
    table_rows = "".join(rows)

    # Rule cards
    cards = []
    for rule in rules:
        scope_str = escape(", ".join(
            f"{k}={v}" for k, v in rule.scope.items() if v is not None
        )) or "<span class='na'>global</span>"
        activated = rule.activated_at or None
        badge = (
            '<span class="badge badge-active">activated</span>'
            if activated else
            '<span class="badge badge-draft">draft</span>'
        )
        card_cls = "rule-card"
        if activated:
            card_cls += " activated"

        preview_section = ""
        if rule.preview_stats:
            preview_section = (
                "<strong>Preview stats</strong>"
                + _preview_html(rule.preview_stats)
            )

        measure_section = ""
        if rule.measure_result:
            measure_section = (
                "<strong>Before/after measurement</strong>"
                + _measure_html(rule.measure_result)
            )

        activated_str = escape(activated) if activated else "not yet activated"

        cards.append(
            f'<div class="{card_cls}">'
            f'<div class="rule-header">'
            f'<span class="rule-id">{escape(rule.rule_id)}</span>'
            f'<span class="sig">{escape(rule.signature)}</span>'
            f'{badge}'
            f'<span class="meta">cluster: {rule.cluster_size} sessions</span>'
            f'</div>'
            f'<p class="rule-text">{escape(rule.rule_text)}</p>'
            f'<p class="scope-row">scope: {scope_str}</p>'
            f'<p class="meta">drafted: {escape(rule.drafted_at[:10])} '
            f'&nbsp;|&nbsp; activated: {activated_str}</p>'
            f'{preview_section}'
            f'{measure_section}'
            f'</div>'
        )

    cards_html = "".join(cards)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>dejavu report</title>
  <style>{_STYLE}</style>
</head>
<body>
  <h1>dejavu analysis report</h1>
  <p class="meta">Generated: {now}</p>

  {summary_grid}

  <h2>Top mistake clusters</h2>
  <table>
    <thead>
      <tr><th>ID</th><th>Signature</th><th>Sessions</th><th>Rule (draft)</th></tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>

  <h2>Rules</h2>
  {cards_html}

  <div class="note-box">
    Before/after comparisons are observational: past sessions cannot be replayed
    with the rule active. Mistake detection is heuristic and may miss cases.
    Thresholds were tuned on a small synthetic set.
  </div>
</body>
</html>"""

    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
