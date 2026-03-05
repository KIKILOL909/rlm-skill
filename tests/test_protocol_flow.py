#!/usr/bin/env python3
"""Integration test: verify all protocol event types log correctly and dashboard renders."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import stats


def test_full_protocol_flow(tmp_path):
    """Simulate a complete 6-step protocol and verify stats capture everything."""
    stats.STATS_DIR = tmp_path
    stats.STATS_FILE = tmp_path / "events.jsonl"

    # Simulate full protocol on a 2MB file
    file_size = 2 * 1024 * 1024
    stats.log_event("rlm_metadata", "server.log", file_size, 2)
    stats.log_event("rlm_peek", "server.log", file_size, 2)
    stats.log_event("rlm_search", "server.log", file_size, 2)
    # 5 sub-queries in ANALYZE
    for i in range(5):
        stats.log_event("rlm_analyze", "server.log", file_size // 5, 2)
    stats.log_event("rlm_synthesize", "server.log", file_size, 2)
    stats.log_event("rlm_submit", "server.log", file_size, 2)

    events = stats.read_events()
    assert len(events) == 10, f"Expected 10 events, got {len(events)}"

    result = stats.compute_stats(events)

    # Pattern breakdown
    assert result["by_pattern"][2] == 10

    # Protocol breakdown
    assert result["by_protocol"]["rlm_metadata"] == 1
    assert result["by_protocol"]["rlm_peek"] == 1
    assert result["by_protocol"]["rlm_search"] == 1
    assert result["by_protocol"]["rlm_analyze"] == 5
    assert result["by_protocol"]["rlm_synthesize"] == 1
    assert result["by_protocol"]["rlm_submit"] == 1

    # Dashboard renders without error
    stats.print_dashboard(result)
    print("\nPASS: test_full_protocol_flow")


def test_mixed_old_and_new_events(tmp_path):
    """Old events and new protocol events coexist in stats."""
    stats.STATS_DIR = tmp_path
    stats.STATS_FILE = tmp_path / "events.jsonl"

    # Old-style event
    stats.log_event("large_file_detected", "old.csv", 1000000, 1)
    # New protocol events
    stats.log_event("rlm_metadata", "new.json", 800000, 2)
    stats.log_event("rlm_submit", "new.json", 800000, 2)

    events = stats.read_events()
    result = stats.compute_stats(events)

    assert result["total_events"] == 3
    assert result["by_pattern"][1] == 1
    assert result["by_pattern"][2] == 2
    assert result["by_protocol"]["rlm_metadata"] == 1
    assert result["by_protocol"]["rlm_submit"] == 1

    stats.print_dashboard(result)
    print("PASS: test_mixed_old_and_new_events")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        test_full_protocol_flow(Path(td))
    with tempfile.TemporaryDirectory() as td:
        test_mixed_old_and_new_events(Path(td))
