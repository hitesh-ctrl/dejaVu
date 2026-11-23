"""
Tests that assert the exact ground-truth numbers from gen_samples.py.

ground_truth.json planted answers:
  edit_without_read   : 11 sessions (9 early, 2 late)
  tests_wrong_folder  : 8 sessions
  user_correction     : 6 sessions
  scope tool=Edit     : fires in 30, mistake in 11, false hits 19
  activation after idx 24 -> before: 9/25, after: 2/22
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SAMPLES = Path(__file__).parent.parent / "samples"
TRUTH = SAMPLES / "ground_truth.json"

# Skip all tests if samples haven't been generated yet
pytestmark = pytest.mark.skipif(
    not SAMPLES.exists() or not TRUTH.exists(),
    reason="Run 'python3 gen_samples.py samples/' first",
)

sys.path.insert(0, str(Path(__file__).parent.parent))

from dejavu.parser import load_sessions
from dejavu.detector import build_sig_map, detect_mistakes
from dejavu.store import Rule
from dejavu.preview import preview_rule
from dejavu.measure import measure_rule


def _load() -> tuple[list, dict]:
    sessions = load_sessions(SAMPLES)
    truth = json.loads(TRUTH.read_text())
    return sessions, truth


def test_session_count():
    sessions, truth = _load()
    assert len(sessions) == truth["total_sessions"]


def test_edit_without_read_cluster():
    sessions, truth = _load()
    sig_map = build_sig_map(sessions)
    expected = truth["mistakes"]["edit_without_read"]["sessions"]
    assert sig_map.get("Edit:file_not_read", set()).__len__() == expected, (
        f"Expected {expected} sessions with Edit:file_not_read"
    )


def test_tests_wrong_folder_cluster():
    sessions, truth = _load()
    sig_map = build_sig_map(sessions)
    expected = truth["mistakes"]["tests_wrong_folder"]["sessions"]
    assert sig_map.get("Bash:enoent:package.json", set()).__len__() == expected


def test_user_correction_cluster():
    sessions, truth = _load()
    sig_map = build_sig_map(sessions)
    expected = truth["mistakes"]["user_correction"]["sessions"]
    assert sig_map.get("user_correction", set()).__len__() == expected


def test_edit_without_read_is_top_cluster():
    sessions, _ = _load()
    sig_map = build_sig_map(sessions)
    top_sig, top_sessions = max(sig_map.items(), key=lambda x: len(x[1]))
    assert top_sig == "Edit:file_not_read"
    assert len(top_sessions) == 11


def test_preview_scope_fires_in_30():
    sessions, truth = _load()
    sig_map = build_sig_map(sessions)

    rule = Rule(
        rule_id="r001",
        signature="Edit:file_not_read",
        cluster_size=11,
        example_sessions=[],
        rule_text="Before calling Edit, verify you have read the file.",
        scope={"tool": "Edit", "command_pattern": None},
        drafted_at="2026-01-01T00:00:00+00:00",
    )

    expected_fires = truth["scope_before_edit"]["sessions_where_rule_fires"]
    expected_mistakes = truth["scope_before_edit"]["sessions_with_mistake"]
    expected_false = expected_fires - expected_mistakes

    p = preview_rule(rule, sessions, sig_map)
    assert p["fires_in_sessions"] == expected_fires, (
        f"Expected scope to fire in {expected_fires} sessions, got {p['fires_in_sessions']}"
    )
    assert p["mistake_in_sessions"] == expected_mistakes
    assert p["false_hits"] == expected_false


def test_measure_before_after():
    sessions, truth = _load()
    # Sessions are sorted by start_time; activation is after index 24
    activation_idx = truth["rule_activation_after_session_index"]
    expected_early = truth["early_block_sessions"]
    expected_late = truth["late_block_sessions"]
    expected_b_mistakes = truth["mistakes"]["edit_without_read"]["early"]
    expected_a_mistakes = truth["mistakes"]["edit_without_read"]["late"]

    # Set activated_at to 1 second after session[activation_idx] starts
    pivot = sessions[activation_idx]
    pivot_dt = datetime.fromisoformat(pivot.start_time.rstrip("Z")).replace(
        tzinfo=timezone.utc
    )
    activated_at = (pivot_dt + timedelta(seconds=1)).isoformat()

    rule = Rule(
        rule_id="r001",
        signature="Edit:file_not_read",
        cluster_size=11,
        example_sessions=[],
        rule_text="Before calling Edit, verify you have read the file.",
        scope={"tool": "Edit", "command_pattern": None},
        drafted_at="2026-01-01T00:00:00+00:00",
        activated_at=activated_at,
    )

    result = measure_rule(rule, sessions)
    assert "error" not in result

    assert result["before"]["sessions"] == expected_early
    assert result["before"]["mistakes"] == expected_b_mistakes
    assert result["after"]["sessions"] == expected_late
    assert result["after"]["mistakes"] == expected_a_mistakes


def test_noise_does_not_form_large_cluster():
    sessions, _ = _load()
    sig_map = build_sig_map(sessions)
    # Noise errors are like Bash:enoent:missing-dir-N (unique per session).
    # No single noise signature should have more than 1 session.
    for sig, sids in sig_map.items():
        if "missing-dir" in sig:
            assert len(sids) == 1, (
                f"Noise signature '{sig}' clustered {len(sids)} sessions (expected 1)"
            )
