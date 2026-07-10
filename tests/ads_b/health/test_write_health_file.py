import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ads_b.health.feeder_stats import FeederStats
from ads_b.health.write_health_file import write_health_file

WRITE_INTERVAL = 300.0


def _dt(second: int) -> datetime:
    """Build a fixed UTC datetime at a given second for deterministic tests."""
    return datetime(2026, 7, 10, 18, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=second)


def test_writes_valid_json_with_healthy_status(tmp_path: Path) -> None:
    """A recent publish yields status 'healthy' and valid JSON on disk."""
    path = tmp_path / 'health.json'
    stats = FeederStats(started_at=_dt(0))
    stats.record_publish(_dt(10))  # publish 10s before the write

    write_health_file(str(path), stats, _dt(20), WRITE_INTERVAL, in_flight=4)

    data = json.loads(path.read_text())
    assert data['status'] == 'healthy'
    assert data['lines_total'] == 1
    assert data['messages_total'] == 1
    assert data['publishes_in_flight'] == 4


def test_stale_when_no_publish(tmp_path: Path) -> None:
    """With no publish recorded, status is 'stale'."""
    path = tmp_path / 'health.json'
    stats = FeederStats(started_at=_dt(0))

    write_health_file(str(path), stats, _dt(20), WRITE_INTERVAL, in_flight=4)

    data = json.loads(path.read_text())
    assert data['status'] == 'stale'


def test_stale_when_publish_too_old(tmp_path: Path) -> None:
    """A publish older than 2x the interval yields status 'stale'."""
    path = tmp_path / 'health.json'
    stats = FeederStats(started_at=_dt(0))
    stats.record_publish(_dt(0))  # publish at t=0

    # Write at t=700, which is > 2*300=600 seconds after the publish.
    write_health_file(str(path), stats, _dt(700), WRITE_INTERVAL, in_flight=4)

    data = json.loads(path.read_text())
    assert data['status'] == 'stale'


def test_overwrites_and_resets_interval(tmp_path: Path) -> None:
    """The file is overwritten each write and the interval delta resets."""
    path = tmp_path / 'health.json'
    stats = FeederStats(started_at=_dt(0))
    stats.record_publish(_dt(10))

    write_health_file(str(path), stats, _dt(20), WRITE_INTERVAL, in_flight=4)
    first = json.loads(path.read_text())
    assert first['lines_last_interval'] == 1
    assert stats.lines_since_write == 0  # reset after write

    stats.record_publish(_dt(30))
    write_health_file(str(path), stats, _dt(40), WRITE_INTERVAL, in_flight=4)
    second = json.loads(path.read_text())

    # Overwrite (not append): totals accumulate, interval delta resets.
    assert second['lines_total'] == 2
    assert second['lines_last_interval'] == 1


def test_leaves_no_temp_file(tmp_path: Path) -> None:
    """After a successful write only the health file remains (temp is renamed)."""
    path = tmp_path / 'health.json'
    stats = FeederStats(started_at=_dt(0))
    stats.record_publish(_dt(1))

    write_health_file(str(path), stats, _dt(2), WRITE_INTERVAL, in_flight=4)

    # The directory holds exactly the health file, no leftover temp.
    assert [p.name for p in tmp_path.iterdir()] == ['health.json']
