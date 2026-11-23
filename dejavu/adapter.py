"""
Generic input adapter.

Accepts a simple JSON format so logs from other agent frameworks can be
analyzed without converting to Claude Code's JSONL format.

Generic session format (one .json file per session):

    {
      "session_id": "optional",
      "start_time": "optional ISO timestamp",
      "cwd": "optional",
      "events": [
        {"type": "user_msg",    "content": "...",              "timestamp": "..."},
        {"type": "tool_use",    "tool_name": "Edit",
                                "tool_input": {"file_path": "src/app.py"},
                                "tool_use_id": "t1",           "timestamp": "..."},
        {"type": "tool_result", "tool_use_id": "t1",
                                "tool_name": "Edit",
                                "content": "File has not been read yet.",
                                "is_error": true,              "timestamp": "..."}
      ]
    }

A file may also be a bare list of events (session_id derived from filename).
A single file may contain a list of session objects.
"""
from __future__ import annotations
import json
from pathlib import Path
from .parser import Session, Event

_SKIP_FILES = {"ground_truth.json"}


def _parse_events(raw: list[dict], offset: int = 0) -> list[Event]:
    events: list[Event] = []
    for i, ev in enumerate(raw):
        t = ev.get("type", "")
        ts = ev.get("timestamp", "")
        if t == "user_msg":
            events.append(Event(
                idx=offset + i,
                kind="user_msg",
                timestamp=ts,
                content=ev.get("content", ""),
            ))
        elif t == "tool_use":
            events.append(Event(
                idx=offset + i,
                kind="tool_use",
                timestamp=ts,
                tool_name=ev.get("tool_name"),
                tool_input=ev.get("tool_input") or {},
                tool_use_id=ev.get("tool_use_id"),
            ))
        elif t == "tool_result":
            content = ev.get("content", "")
            is_error = bool(ev.get("is_error", False))
            if not is_error and "Exit code 1" in str(content):
                is_error = True
            events.append(Event(
                idx=offset + i,
                kind="tool_result",
                timestamp=ts,
                tool_name=ev.get("tool_name"),
                tool_input=ev.get("tool_input") or {},
                tool_use_id=ev.get("tool_use_id"),
                content=str(content),
                is_error=is_error,
            ))
    return events


def _session_from_dict(data: dict, default_id: str) -> Session:
    s = Session(
        session_id=data.get("session_id") or default_id,
        file_path="",
        start_time=data.get("start_time") or "",
        cwd=data.get("cwd") or "",
    )
    s.events = _parse_events(data.get("events") or [])
    if not s.start_time and s.events:
        s.start_time = s.events[0].timestamp
    return s


def load_generic_file(path: Path) -> list[Session]:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    stem = path.stem

    # List at top level: either list of sessions or list of events
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and "events" in data[0]:
            return [_session_from_dict(d, f"{stem}-{i}") for i, d in enumerate(data)]
        # Bare list of events -> single session
        s = Session(session_id=stem, file_path=str(path), start_time="", cwd="")
        s.events = _parse_events(data)
        if s.events:
            s.start_time = s.events[0].timestamp
        return [s]

    if isinstance(data, dict):
        return [_session_from_dict(data, stem)]

    return []


def load_generic_sessions(directory: str | Path) -> list[Session]:
    directory = Path(directory)
    sessions: list[Session] = []
    for path in sorted(directory.glob("*.json")):
        if path.name in _SKIP_FILES:
            continue
        sessions.extend(load_generic_file(path))
    sessions.sort(key=lambda s: s.start_time)
    return sessions


def is_generic_dir(directory: str | Path) -> bool:
    """True if the directory has .json files but no .jsonl files."""
    p = Path(directory)
    has_jsonl = any(p.glob("*.jsonl"))
    has_json = any(f for f in p.glob("*.json") if f.name not in _SKIP_FILES)
    return has_json and not has_jsonl
