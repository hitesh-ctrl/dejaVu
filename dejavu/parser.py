from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json

SKIP_TYPES = {
    "file-history-snapshot", "file-history-delta", "queue-operation",
    "last-prompt", "atis-latch", "api-request", "api-request-shape",
    "api-request-blob", "cost-state", "relocated", "derived-from",
    "bridge-session", "pr-link", "tools-used", "custom-title",
    "agent-name", "mode",
}


@dataclass
class Event:
    idx: int
    kind: str          # user_msg | tool_use | tool_result | hook_injection
    timestamp: str
    tool_name: str | None = None
    tool_input: dict = field(default_factory=dict)
    tool_use_id: str | None = None
    content: str = ""
    is_error: bool = False
    is_sidechain: bool = False


@dataclass
class Session:
    session_id: str
    file_path: str
    start_time: str
    cwd: str
    events: list[Event] = field(default_factory=list)
    is_subagent: bool = False


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                t = b.get("type", "")
                if t == "text":
                    parts.append(b.get("text", ""))
                elif t == "tool_result":
                    c = b.get("content", "")
                    parts.append(_content_text(c))
        return "\n".join(p for p in parts if p)
    return ""


def parse_file(path: Path) -> Session | None:
    path = Path(path)
    fname = path.name
    is_subagent = fname.startswith("agent-")

    raw_lines: list[dict] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        raw_lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return None

    if not raw_lines:
        return None

    first = next(
        (l for l in raw_lines if l.get("type") in ("user", "assistant", "system")),
        raw_lines[0],
    )
    session_id = first.get("sessionId", path.stem)
    start_time = first.get("timestamp", "")
    cwd = first.get("cwd", "")

    session = Session(
        session_id=session_id,
        file_path=str(path),
        start_time=start_time,
        cwd=cwd,
        is_subagent=is_subagent,
    )

    # tool_use_id -> (tool_name, tool_input)
    pending: dict[str, tuple[str, dict]] = {}

    for obj in raw_lines:
        t = obj.get("type", "")
        if t in SKIP_TYPES:
            continue

        is_sc = bool(obj.get("isSidechain", False))
        ts = obj.get("timestamp", "")

        if t == "assistant":
            blocks = obj.get("message", {}).get("content", [])
            if not isinstance(blocks, list):
                continue
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    tid = b.get("id", "")
                    tname = b.get("name", "")
                    tinput = b.get("input", {}) or {}
                    pending[tid] = (tname, tinput)
                    session.events.append(Event(
                        idx=len(session.events),
                        kind="tool_use",
                        timestamp=ts,
                        tool_name=tname,
                        tool_input=tinput,
                        tool_use_id=tid,
                        is_sidechain=is_sc,
                    ))

        elif t == "user":
            if obj.get("isCompactSummary"):
                continue
            msg_content = obj.get("message", {}).get("content", "")

            if isinstance(msg_content, str):
                session.events.append(Event(
                    idx=len(session.events),
                    kind="user_msg",
                    timestamp=ts,
                    content=msg_content,
                    is_sidechain=is_sc,
                ))

            elif isinstance(msg_content, list):
                for b in msg_content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_result":
                        tid = b.get("tool_use_id", "")
                        raw_c = b.get("content", "")
                        c = _content_text(raw_c) if isinstance(raw_c, list) else str(raw_c)
                        is_error = bool(b.get("is_error", False))
                        # Secondary signal: Bash exit code 1 without is_error flag
                        if not is_error and "Exit code 1" in c:
                            is_error = True
                        tname, tinput = pending.get(tid, ("", {}))
                        session.events.append(Event(
                            idx=len(session.events),
                            kind="tool_result",
                            timestamp=ts,
                            tool_name=tname,
                            tool_input=tinput,
                            tool_use_id=tid,
                            content=c,
                            is_error=is_error,
                            is_sidechain=is_sc,
                        ))

        elif t == "system":
            if obj.get("subtype") == "stop_hook_summary":
                ctx = obj.get("hookAdditionalContext")
                if ctx:
                    session.events.append(Event(
                        idx=len(session.events),
                        kind="hook_injection",
                        timestamp=ts,
                        content=ctx if isinstance(ctx, str) else str(ctx),
                        is_sidechain=is_sc,
                    ))

    return session


def load_sessions(
    directory: str | Path,
    skip_subagents: bool = True,
) -> list[Session]:
    directory = Path(directory)
    sessions = []
    for path in sorted(directory.glob("*.jsonl")):
        s = parse_file(path)
        if s is None:
            continue
        if skip_subagents and s.is_subagent:
            continue
        sessions.append(s)
    sessions.sort(key=lambda s: s.start_time)
    return sessions


def load_all_project_sessions(
    projects_dir: str | Path | None = None,
    skip_subagents: bool = True,
) -> list[Session]:
    if projects_dir is None:
        projects_dir = Path.home() / ".claude" / "projects"
    projects_dir = Path(projects_dir)
    sessions = []
    for project_dir in sorted(projects_dir.iterdir()):
        if project_dir.is_dir():
            for path in sorted(project_dir.glob("*.jsonl")):
                s = parse_file(path)
                if s is None:
                    continue
                if skip_subagents and s.is_subagent:
                    continue
                sessions.append(s)
    sessions.sort(key=lambda s: s.start_time)
    return sessions


def load_sessions_from(
    path: str | Path | None,
    skip_subagents: bool = True,
) -> list[Session]:
    if path is None:
        return load_all_project_sessions(skip_subagents=skip_subagents)
    p = Path(path)
    # If the directory directly contains .jsonl files, load from it
    if list(p.glob("*.jsonl")):
        return load_sessions(p, skip_subagents=skip_subagents)
    # Otherwise treat as projects directory (subdirs with .jsonl files)
    return load_all_project_sessions(p, skip_subagents=skip_subagents)
