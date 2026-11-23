from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from html import escape
from .store import Rule
from .parser import Session

_STYLE = """
body { font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #222; }
h1 { font-size: 1.4rem; color: #111; }
h2 { font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
.meta { color: #666; font-size: 0.9rem; margin-bottom: 2rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; margin-bottom: 1.5rem; }
th { background: #f5f5f5; text-align: left; padding: 8px 10px; border: 1px solid #ddd; }
td { padding: 7px 10px; border: 1px solid #ddd; vertical-align: top; }
tr:nth-child(even) { background: #fafafa; }
.rule-card { border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; margin-bottom: 16px; }
.rule-id { font-weight: bold; color: #333; font-family: monospace; }
.sig { font-family: monospace; background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }
.rule-text { margin: 8px 0 4px; }
.scope { font-family: monospace; font-size: 0.85rem; color: #555; }
.warning { color: #b45309; font-size: 0.85rem; }
.stat-good { color: #166534; }
.stat-warn { color: #b45309; }
p.note { font-size: 0.85rem; color: #666; }
"""


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{100 * n / total:.0f}%"


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

    rows = []
    rule_map = {r.rule_id: r for r in rules}
    for rule in rules:
        # Find preview stats if stored (we regenerate from scratch here)
        rows.append(f"""
        <tr>
          <td><span class="rule-id">{escape(rule.rule_id)}</span></td>
          <td><span class="sig">{escape(rule.signature)}</span></td>
          <td>{rule.cluster_size}</td>
          <td>{escape(rule.rule_text)}</td>
        </tr>""")

    table_rows = "".join(rows)

    cards = []
    for rule in rules:
        scope_str = ", ".join(
            f"{k}={escape(str(v))}"
            for k, v in rule.scope.items()
            if v is not None
        )
        activated = rule.activated_at or "not yet activated"
        cards.append(f"""
        <div class="rule-card">
          <div>
            <span class="rule-id">{escape(rule.rule_id)}</span>
            &nbsp; <span class="sig">{escape(rule.signature)}</span>
            &nbsp; <span class="meta">({rule.cluster_size} sessions)</span>
          </div>
          <p class="rule-text"><strong>Rule:</strong> {escape(rule.rule_text)}</p>
          <p class="scope"><strong>Scope:</strong> {scope_str}</p>
          <p class="meta">Activated: {escape(activated)}</p>
        </div>""")

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
  <p class="meta">Generated: {now} &nbsp;|&nbsp; Sessions analyzed: {n}</p>

  <h2>Top mistake clusters</h2>
  <table>
    <thead>
      <tr><th>ID</th><th>Signature</th><th>Sessions</th><th>Rule (draft)</th></tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>

  <h2>Rules</h2>
  {cards_html}

  <p class="note">
    Before/after comparisons are observational: old sessions cannot be replayed with
    the rule on. Mistake detection is heuristic and may miss cases. Thresholds were
    tuned on a small synthetic set.
  </p>
</body>
</html>"""

    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
