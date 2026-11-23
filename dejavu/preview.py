from __future__ import annotations
import re
from .parser import Session, Event
from .store import Rule


def _event_matches_scope(scope: dict, ev: Event) -> bool:
    if ev.kind != "tool_use":
        return False
    tool = scope.get("tool")
    if tool and ev.tool_name != tool:
        return False
    pat = scope.get("command_pattern")
    if pat:
        cmd = ev.tool_input.get("command", "") or ""
        if not re.search(pat, cmd, re.IGNORECASE):
            return False
    fpat = scope.get("file_pattern")
    if fpat:
        fpath = ev.tool_input.get("file_path", "") or ""
        if not re.search(fpat, fpath, re.IGNORECASE):
            return False
    return True


def preview_rule(
    rule: Rule,
    sessions: list[Session],
    sig_map: dict[str, set[str]],
    scope_override: dict | None = None,
) -> dict:
    scope = scope_override if scope_override is not None else rule.scope
    mistake_sessions = sig_map.get(rule.signature, set())

    fires_in: list[str] = []
    mistake_in: list[str] = []

    for s in sessions:
        for ev in s.events:
            if _event_matches_scope(scope, ev):
                fires_in.append(s.session_id)
                if s.session_id in mistake_sessions:
                    mistake_in.append(s.session_id)
                break  # count each session once

    false_hits = len(fires_in) - len(mistake_in)
    return {
        "scope": scope,
        "fires_in_sessions": len(fires_in),
        "mistake_in_sessions": len(mistake_in),
        "false_hits": false_hits,
        "total_sessions": len(sessions),
        "example_fire_sessions": fires_in[:5],
        "example_false_sessions": [s for s in fires_in if s not in set(mistake_in)][:3],
    }
