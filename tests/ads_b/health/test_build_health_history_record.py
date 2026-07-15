from datetime import datetime, timezone

from ads_b.health.feeder_stats import FeederStats
from ads_b.health.build_health_history_record import build_health_history_record


def _stats() -> FeederStats:
    """A FeederStats with a known start time for deterministic assertions."""
    return FeederStats(started_at=datetime(2026, 7, 15, 4, 0, 0, tzinfo=timezone.utc))


def test_record_has_ts_delta_and_snapshot_fields() -> None:
    """The record carries ts, the delta, and the full snapshot (incl. started_at)."""
    now = datetime(2026, 7, 15, 5, 0, 0, tzinfo=timezone.utc)
    stats = _stats()
    stats.record_publish(now)  # one line, so snapshot has non-zero counters

    record = build_health_history_record(
        stats, now, in_flight=3, lines_this_interval=7
    )

    # Top-level additions.
    assert record['ts'] == now.isoformat()
    assert record['lines_this_interval'] == 7
    # Snapshot fields are merged in, including the run identifier.
    assert record['started_at'] == stats.started_at.isoformat()
    assert record['uptime_seconds'] == 3600
    assert record['publishes_in_flight'] == 3
