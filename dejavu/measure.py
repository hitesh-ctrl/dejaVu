from __future__ import annotations
import math
from datetime import datetime, timezone
from .parser import Session
from .store import Rule
from .detector import detect_mistakes


def _parse_ts(ts: str) -> datetime:
    ts = ts.rstrip("Z")
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def measure_rule(rule: Rule, sessions: list[Session]) -> dict:
    if not rule.activated_at:
        return {"error": "Rule not activated. Run 'emit' first."}

    act_dt = _parse_ts(rule.activated_at)

    before: list[Session] = []
    after: list[Session] = []
    for s in sessions:
        if not s.start_time:
            continue
        try:
            s_dt = _parse_ts(s.start_time)
        except ValueError:
            continue
        if s_dt < act_dt:
            before.append(s)
        else:
            after.append(s)

    def count_mistakes(session_list: list[Session]) -> int:
        n = 0
        for s in session_list:
            signals = detect_mistakes(s)
            if any(sig.signature == rule.signature for sig in signals):
                n += 1
        return n

    b_total = len(before)
    a_total = len(after)
    b_mistakes = count_mistakes(before)
    a_mistakes = count_mistakes(after)

    b_rate = b_mistakes / b_total if b_total else 0.0
    a_rate = a_mistakes / a_total if a_total else 0.0

    return {
        "before": {
            "sessions": b_total,
            "mistakes": b_mistakes,
            "rate": round(b_rate, 4),
            "ci_95": tuple(round(x, 4) for x in _wilson_ci(b_mistakes, b_total)),
        },
        "after": {
            "sessions": a_total,
            "mistakes": a_mistakes,
            "rate": round(a_rate, 4),
            "ci_95": tuple(round(x, 4) for x in _wilson_ci(a_mistakes, a_total)),
        },
        "small_sample_warning": a_total < 20,
        "note": (
            "This is an observational before/after comparison, not a controlled test. "
            "Old sessions cannot be replayed with the rule on."
        ),
    }
