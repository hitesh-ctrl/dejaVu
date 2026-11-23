from __future__ import annotations
import re
from dataclasses import dataclass
from .parser import Session, Event

CORRECTION_PATTERNS = [
    r"^no[,\.!\s]",
    r"^that'?s wrong",
    r"\bi said\b",
    r"^don'?t do that",
    r"^stop[,\s]",
    r"not what i (asked|wanted|said|meant)",
    r"i didn'?t (ask|say|want)",
    r"^wrong[,\.\s]",
    r"^incorrect[,\.\s]",
    r"^please don'?t",
]

_correction_re = re.compile("|".join(CORRECTION_PATTERNS), re.IGNORECASE)


@dataclass
class MistakeSignal:
    signature: str
    session_id: str
    event_idx: int
    tool_name: str
    content_snippet: str


def _error_signature(tool_name: str, content: str) -> str:
    c = content.lower()

    if tool_name == "Edit" and "not been read" in c:
        return "Edit:file_not_read"

    if "enoent" in c or "no such file" in c:
        # Try to pull out the specific filename so noise stays unique
        m = re.search(r"['\"]([^'\"]+)['\"]", content)
        if m:
            stem = m.group(1).replace("\\", "/").split("/")[-1]
            return f"{tool_name}:enoent:{stem}"
        m = re.search(r"read\s+(\S+?):", content, re.IGNORECASE)
        if m:
            return f"{tool_name}:enoent:{m.group(1)}"
        return f"{tool_name}:enoent"

    if "permission" in c and ("denied" in c or "rejected" in c):
        return f"{tool_name}:permission_denied"

    if "does not exist" in c or "not found" in c:
        return f"{tool_name}:not_found"

    words = re.sub(r"[^a-z0-9 ]", " ", c).split()[:3]
    return f"{tool_name}:error:{'_'.join(words)}"


def detect_mistakes(session: Session) -> list[MistakeSignal]:
    signals: list[MistakeSignal] = []

    for ev in session.events:
        if ev.kind == "tool_result" and ev.is_error:
            sig = _error_signature(ev.tool_name or "", ev.content)
            signals.append(MistakeSignal(
                signature=sig,
                session_id=session.session_id,
                event_idx=ev.idx,
                tool_name=ev.tool_name or "",
                content_snippet=ev.content[:120],
            ))

        elif ev.kind == "user_msg" and _correction_re.search(ev.content):
            signals.append(MistakeSignal(
                signature="user_correction",
                session_id=session.session_id,
                event_idx=ev.idx,
                tool_name="",
                content_snippet=ev.content[:120],
            ))

    return signals


def build_sig_map(sessions: list[Session]) -> dict[str, set[str]]:
    """Return signature -> set of session_ids (deduplicated per session)."""
    result: dict[str, set[str]] = {}
    for s in sessions:
        seen_sigs: set[str] = set()
        for signal in detect_mistakes(s):
            if signal.signature not in seen_sigs:
                result.setdefault(signal.signature, set()).add(s.session_id)
                seen_sigs.add(signal.signature)
    return result
