from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import json


@dataclass
class Rule:
    rule_id: str
    signature: str
    cluster_size: int
    example_sessions: list[str]
    rule_text: str
    scope: dict
    drafted_at: str
    activated_at: Optional[str] = None
    preview_stats: Optional[dict] = None   # cached from last `preview` run
    measure_result: Optional[dict] = None  # cached from last `measure` run


@dataclass
class RuleStore:
    path: Path
    _rules: dict[str, Rule] = field(default_factory=dict, repr=False)
    sessions_dir: Optional[str] = None
    session_count: int = 0

    def __post_init__(self):
        self.path = Path(self.path)
        if self.path.exists():
            self._load()

    def _load(self):
        data = json.loads(self.path.read_text())
        self.sessions_dir = data.get("sessions_dir")
        self.session_count = data.get("session_count", 0)
        for d in data.get("rules", []):
            r = Rule(**d)
            self._rules[r.rule_id] = r

    def save(self):
        self.path.write_text(json.dumps({
            "sessions_dir": self.sessions_dir,
            "session_count": self.session_count,
            "rules": [asdict(r) for r in self._rules.values()],
        }, indent=2))

    def add(self, rule: Rule) -> None:
        self._rules[rule.rule_id] = rule

    def get(self, rule_id: str) -> Optional[Rule]:
        return self._rules.get(rule_id)

    def all(self) -> list[Rule]:
        return list(self._rules.values())
