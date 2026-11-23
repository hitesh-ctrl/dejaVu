from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from html import escape
from .store import Rule
from .parser import Session

_CSS = """
<style>
:root {
  --bg: #212121;
  --s1: #2f2f2f;
  --s2: #3a3a3a;
  --border: rgba(255,255,255,.1);
  --fg: #ececec;
  --muted: #8e8ea0;
  --dim: #565869;
  --teal: #10a37f;
  --teal-soft: rgba(16,163,127,.12);
  --teal-border: rgba(16,163,127,.22);
  --success: #10a37f;
  --warn: #f5a623;
  --danger: #ef4444;
  color-scheme: dark;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) {
    --bg: #f9f9f9; --s1: #ffffff; --s2: #f4f4f4;
    --border: rgba(0,0,0,.08); --fg: #0d0d0d;
    --muted: #6e6e80; --dim: #aeaec0;
    --teal: #0a906f; --teal-soft: rgba(10,144,111,.08);
    --teal-border: rgba(10,144,111,.18);
    --success: #0a906f; --warn: #c27d0d; --danger: #dc2626;
    color-scheme: light;
  }
}
:root[data-theme="light"] {
  --bg: #f9f9f9; --s1: #ffffff; --s2: #f4f4f4;
  --border: rgba(0,0,0,.08); --fg: #0d0d0d;
  --muted: #6e6e80; --dim: #aeaec0;
  --teal: #0a906f; --teal-soft: rgba(10,144,111,.08);
  --teal-border: rgba(10,144,111,.18);
  --success: #0a906f; --warn: #c27d0d; --danger: #dc2626;
  color-scheme: light;
}
*,*::before,*::after{box-sizing:border-box}
body{
  background:var(--bg);color:var(--fg);
  font-family:'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
  font-size:15px;line-height:1.65;margin:0;
  padding-block:calc(env(safe-area-inset-top,0px) + 48px) calc(env(safe-area-inset-bottom,0px) + 72px);
  padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px));
}
.wrap{max-width:680px;margin:0 auto}
.hd{margin-bottom:40px}
.hd-top{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.hd-mark{width:28px;height:28px;border-radius:50%;background:var(--teal);display:flex;align-items:center;justify-content:center;flex-shrink:0}
.hd-mark svg{width:14px;height:14px;fill:#fff}
.hd-name{font-size:17px;font-weight:600}
.hd-ts{font-size:13px;color:var(--muted)}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:36px}
.stat-pill{display:flex;align-items:center;gap:7px;background:var(--s1);border:1px solid var(--border);border-radius:10px;padding:10px 16px;flex:1;min-width:100px}
.stat-n{font-size:22px;font-weight:600;line-height:1;font-variant-numeric:tabular-nums;letter-spacing:-.3px}
.stat-n.t{color:var(--teal)}
.stat-label{font-size:12px;color:var(--muted)}
.dl{display:flex;align-items:center;gap:12px;margin-bottom:14px;margin-top:32px}
.dl span{font-size:12px;font-weight:500;letter-spacing:.04em;color:var(--muted);flex-shrink:0}
.dl::before,.dl::after{content:'';flex:1;height:1px;background:var(--border)}
.clist{display:flex;flex-direction:column}
.ci{display:flex;align-items:flex-start;gap:14px;padding:13px 0;border-bottom:1px solid var(--border)}
.ci:first-child{border-top:1px solid var(--border)}
.ci-rid{font-family:ui-monospace,'SF Mono',Consolas,monospace;font-size:11.5px;color:var(--teal);font-weight:500;padding-top:3px;min-width:32px;flex-shrink:0}
.ci-num{font-family:ui-monospace,'SF Mono',Consolas,monospace;font-size:11px;color:var(--dim);padding-top:3px;min-width:28px}
.ci-body{flex:1;min-width:0}
.ci-sig{font-family:ui-monospace,'SF Mono',Consolas,monospace;font-size:12.5px;color:var(--fg);display:block;margin-bottom:1px}
.ci-desc{font-size:12.5px;color:var(--muted)}
.ci-cnt{font-size:13px;font-weight:500;color:var(--muted);flex-shrink:0;font-variant-numeric:tabular-nums;padding-top:2px}
.rule{background:var(--s1);border:1px solid var(--border);border-radius:14px;padding:20px 22px;margin-bottom:10px}
.rule.on{border-color:var(--teal-border)}
.rule-top{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:12px}
.rule-id{font-family:ui-monospace,'SF Mono',Consolas,monospace;font-size:12px;font-weight:600;color:var(--teal)}
.rule-sig{font-family:ui-monospace,'SF Mono',Consolas,monospace;font-size:12px;color:var(--muted)}
.rule-cnt{font-size:12px;color:var(--dim);margin-left:auto;font-variant-numeric:tabular-nums}
.dot-badge{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;font-weight:500;color:var(--teal)}
.dot-badge::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--teal);flex-shrink:0}
.dot-badge.off{color:var(--dim)}
.dot-badge.off::before{background:var(--dim)}
.rule-text{font-size:14.5px;line-height:1.65;color:var(--fg);margin-bottom:10px;max-width:60ch}
.rule-scope{font-family:ui-monospace,'SF Mono',Consolas,monospace;font-size:11.5px;color:var(--dim);margin-bottom:18px}
.sub-row{display:flex;align-items:center;gap:6px;margin-bottom:10px;margin-top:16px}
.sub-title{font-size:11.5px;font-weight:500;color:var(--muted);letter-spacing:.03em}
.sub-rule{flex:1;height:1px;background:var(--border)}
.sm{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px}
.sm-item{display:flex;flex-direction:column;gap:2px}
.sm-lbl{font-size:11px;color:var(--dim)}
.sm-val{font-size:20px;font-weight:600;letter-spacing:-.3px;line-height:1;font-variant-numeric:tabular-nums}
.sm-val.g{color:var(--success)}
.ci-block{display:flex;flex-direction:column;gap:8px}
.ci-row-b{display:flex;align-items:center;gap:10px}
.ci-lbl-b{font-family:ui-monospace,'SF Mono',Consolas,monospace;font-size:11px;color:var(--muted);width:42px;flex-shrink:0}
.ci-track-b{flex:1;height:5px;background:var(--s2);border-radius:3px;position:relative;overflow:visible;min-width:0}
.ci-range-b{position:absolute;height:100%;border-radius:3px;opacity:.4}
.ci-tick-b{position:absolute;width:2px;height:10px;top:-2.5px;border-radius:1px}
.ci-pct-b{font-family:ui-monospace,'SF Mono',Consolas,monospace;font-size:11px;width:34px;text-align:right;font-variant-numeric:tabular-nums}
.ci-n-b{font-size:11px;color:var(--dim);font-variant-numeric:tabular-nums}
.ci-note-b{font-size:12.5px;color:var(--muted);margin-top:8px;line-height:1.55}
.flash-warn{font-size:12.5px;color:var(--warn);background:rgba(245,166,35,.08);border:1px solid rgba(245,166,35,.2);border-radius:8px;padding:10px 14px;margin-top:8px}
.footer{margin-top:48px;font-size:12.5px;color:var(--dim);line-height:1.65;max-width:56ch;padding-top:20px;border-top:1px solid var(--border)}
@media(max-width:500px){.stat-pill{min-width:80px;padding:9px 12px}.stat-n{font-size:18px}}
</style>
"""

_MARK_SVG = (
    '<svg viewBox="0 0 16 16">'
    '<path d="M8 1.5a6.5 6.5 0 1 0 0 13A6.5 6.5 0 0 0 8 1.5zM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8z"/>'
    '</svg>'
)


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{100 * n / total:.0f}%"


def _rate_str(r: float) -> str:
    return f"{r:.1%}"


def _ci_bar_html(before: dict, after: dict | None) -> str:
    b_lo, b_hi = before["ci_95"]
    b_rate = before["rate"]

    def pct(v: float) -> str:
        return f"{min(max(v * 100, 0), 100):.1f}%"

    rows = [
        f'<div class="ci-row-b">'
        f'<span class="ci-lbl-b">before</span>'
        f'<div class="ci-track-b">'
        f'<div class="ci-range-b" style="left:{pct(b_lo)};width:{pct(b_hi-b_lo)};background:var(--muted)"></div>'
        f'<div class="ci-tick-b" style="left:calc({pct(b_rate)} - 1px);background:var(--muted)"></div>'
        f'</div>'
        f'<span class="ci-pct-b" style="color:var(--fg)">{_rate_str(b_rate)}</span>'
        f'<span class="ci-n-b">n={before["sessions"]}</span>'
        f'</div>'
    ]
    if after:
        a_lo, a_hi = after["ci_95"]
        a_rate = after["rate"]
        color = "var(--success)" if a_rate < b_rate else "var(--danger)"
        rows.append(
            f'<div class="ci-row-b">'
            f'<span class="ci-lbl-b">after</span>'
            f'<div class="ci-track-b">'
            f'<div class="ci-range-b" style="left:{pct(a_lo)};width:{pct(a_hi-a_lo)};background:{color}"></div>'
            f'<div class="ci-tick-b" style="left:calc({pct(a_rate)} - 1px);background:{color}"></div>'
            f'</div>'
            f'<span class="ci-pct-b" style="color:{color}">{_rate_str(a_rate)}</span>'
            f'<span class="ci-n-b">n={after["sessions"]}</span>'
            f'</div>'
        )
    return "".join(rows)


def _preview_section(p: dict) -> str:
    fires = p.get("fires_in_sessions", 0)
    total = p.get("total_sessions", 1)
    mistakes = p.get("mistake_in_sessions", 0)
    false_hits = p.get("false_hits", 0)
    precision = (mistakes / fires) if fires else 0
    prec_cls = "g" if precision >= 0.5 else ""
    return (
        f'<div class="sub-row"><span class="sub-title">Preview</span><span class="sub-rule"></span></div>'
        f'<div class="sm">'
        f'<div class="sm-item"><span class="sm-lbl">Fires in</span>'
        f'<span class="sm-val">{fires}<span style="font-size:13px;color:var(--dim);font-weight:400">/{total}</span></span></div>'
        f'<div class="sm-item"><span class="sm-lbl">True hits</span><span class="sm-val g">{mistakes}</span></div>'
        f'<div class="sm-item"><span class="sm-lbl">False hits</span><span class="sm-val">{false_hits}</span></div>'
        f'<div class="sm-item"><span class="sm-lbl">Precision</span><span class="sm-val {prec_cls}">{precision:.0%}</span></div>'
        f'</div>'
    )


def _measure_section(m: dict) -> str:
    if "error" in m:
        return (
            f'<div class="flash-warn">Measure error: {escape(m["error"])}</div>'
        )
    warn = ""
    if m.get("small_sample_warning"):
        warn = (
            '<div class="flash-warn" style="margin-bottom:10px">'
            'Small sample: fewer than 20 sessions after activation. Results not reliable.'
            '</div>'
        )
    note = m.get("note", "")
    bars = _ci_bar_html(m["before"], m["after"])
    return (
        f'<div class="sub-row"><span class="sub-title">Before / After</span><span class="sub-rule"></span></div>'
        f'{warn}'
        f'<div class="ci-block">{bars}</div>'
        + (f'<p class="ci-note-b">{escape(note)}</p>' if note else "")
    )


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

    # Stat pills
    stat_pills = "".join(
        f'<div class="stat-pill">'
        f'<span class="stat-n{" t" if accent else ""}">{val}</span>'
        f'<span class="stat-label">{label}</span>'
        f'</div>'
        for val, label, accent in [
            (n, "Sessions", False),
            (len(clusters), "Clusters", False),
            (len(rules), "Rules", False),
            (n_activated, "Activated", True),
            (n_measured, "Measured", True),
        ]
    )

    # Cluster list items
    cluster_items = []
    for sig, session_ids in clusters:
        rule = next((r for r in rules if r.signature == sig), None)
        if rule:
            id_cell = f'<span class="ci-rid">{escape(rule.rule_id)}</span>'
            desc = escape(rule.rule_text)
        else:
            id_cell = '<span class="ci-num">—</span>'
            desc = '<span style="color:var(--dim)">no rule drafted</span>'
        sig_color = "" if rule else ' style="color:var(--muted)"'
        cnt_color = "" if rule else ' style="color:var(--dim)"'
        cluster_items.append(
            f'<div class="ci">'
            f'{id_cell}'
            f'<div class="ci-body">'
            f'<span class="ci-sig"{sig_color}>{escape(sig)}</span>'
            f'<span class="ci-desc">{desc}</span>'
            f'</div>'
            f'<span class="ci-cnt"{cnt_color}>{len(session_ids)}</span>'
            f'</div>'
        )

    # Rule cards
    cards = []
    for rule in rules:
        scope_str = escape(", ".join(
            f"{k}={v}" for k, v in rule.scope.items() if v is not None
        )) or '<span style="color:var(--dim)">global</span>'

        activated = rule.activated_at
        badge = (
            '<span class="dot-badge">Activated</span>'
            if activated else
            '<span class="dot-badge off">Draft</span>'
        )
        card_cls = "rule on" if activated else "rule"
        activated_str = escape(activated[:10]) if activated else "not activated"

        preview_html = _preview_section(rule.preview_stats) if rule.preview_stats else ""
        measure_html = _measure_section(rule.measure_result) if rule.measure_result else ""

        cards.append(
            f'<div class="{card_cls}">'
            f'<div class="rule-top">'
            f'<span class="rule-id">{escape(rule.rule_id)}</span>'
            f'<span class="rule-sig">{escape(rule.signature)}</span>'
            f'{badge}'
            f'<span class="rule-cnt">{rule.cluster_size} sessions &nbsp;·&nbsp; {activated_str}</span>'
            f'</div>'
            f'<p class="rule-text">{escape(rule.rule_text)}</p>'
            f'<div class="rule-scope">scope: {scope_str}</div>'
            f'{preview_html}'
            f'{measure_html}'
            f'</div>'
        )

    clusters_html = "".join(cluster_items)
    cards_html = "".join(cards)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="claude:viewport-fit-sides" content="cover">
  <title>dejavu report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap">
  {_CSS}
</head>
<body>
<div class="wrap">

  <header class="hd">
    <div class="hd-top">
      <div class="hd-mark">{_MARK_SVG}</div>
      <span class="hd-name">dejavu</span>
    </div>
    <div class="hd-ts">Analysis report &nbsp;·&nbsp; {now}</div>
  </header>

  <div class="stats">{stat_pills}</div>

  <div class="dl"><span>Top clusters</span></div>
  <div class="clist">{clusters_html}</div>

  <div class="dl" style="margin-top:40px"><span>Rules</span></div>
  {cards_html}

  <p class="footer">Before/after comparisons are observational: past sessions cannot be replayed with the rule active.
  Mistake detection is heuristic and may miss cases. All data remains local.</p>

</div>
</body>
</html>"""

    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
