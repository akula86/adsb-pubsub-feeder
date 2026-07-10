import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from ads_b.health.feeder_stats import FeederStats
from ads_b.health.safe_write_health_file import safe_write_health_file
from ads_b.observability.throttled_logger import ThrottledLogger

WRITE_INTERVAL = 300.0
SAMPLE_COUNT = 5
SUMMARY_INTERVAL_SECONDS = 60.0


def _dt(second: int) -> datetime:
    """Build a fixed UTC datetime at a given second for deterministic tests."""
    return datetime(2026, 7, 10, 18, 0, second, tzinfo=timezone.utc)


def _throttle() -> ThrottledLogger:
    """Build a real ThrottledLogger wired to this module's logger."""
    return ThrottledLogger(
        logging.getLogger(__name__), SAMPLE_COUNT, SUMMARY_INTERVAL_SECONDS, time.monotonic
    )


def test_writes_file_on_success(tmp_path: Path) -> None:
    """A writable path produces the health file."""
    path = tmp_path / 'health.json'
    stats = FeederStats(started_at=_dt(0))
    stats.record_publish(_dt(1))

    safe_write_health_file(str(path), stats, _dt(2), WRITE_INTERVAL, 0, _throttle())

    assert path.exists()


def test_swallows_oserror_and_logs(tmp_path: Path, caplog) -> None:
    """A bad path is caught, logged through the throttle, and does not raise."""
    # A path inside a non-existent directory makes the atomic write raise OSError.
    bad_path = str(tmp_path / 'no_such_dir' / 'health.json')
    stats = FeederStats(started_at=_dt(0))

    with caplog.at_level('ERROR'):
        safe_write_health_file(bad_path, stats, _dt(2), WRITE_INTERVAL, 0, _throttle())

    # No exception propagated, and the failure was logged.
    assert 'Health file write failed' in caplog.text
