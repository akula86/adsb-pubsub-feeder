from datetime import date, datetime, timezone

from ads_b.health.feeder_stats import FeederStats


def _dt(second: int) -> datetime:
    """Build a fixed UTC datetime at a given second for deterministic tests."""
    return datetime(2026, 7, 10, 18, 0, second, tzinfo=timezone.utc)


def _dt_on(day: int, hour: int = 12) -> datetime:
    """A UTC datetime on a given July-2026 day (for cross-day rollover tests)."""
    return datetime(2026, 7, day, hour, 0, 0, tzinfo=timezone.utc)


def test_record_publish_updates_line_message_and_time() -> None:
    """record_publish increments line and message counters and sets last_publish_at."""
    stats = FeederStats(started_at=_dt(0))

    stats.record_publish(_dt(5))
    stats.record_publish(_dt(6))

    assert stats.lines_total == 2
    assert stats.lines_since_write == 2
    assert stats.messages_total == 2
    assert stats.last_publish_at == _dt(6)


def test_record_connect_and_disconnect() -> None:
    """Connect and disconnect update their counters; disconnect sets last_reconnect_at."""
    stats = FeederStats(started_at=_dt(0))

    stats.record_connect()
    stats.record_disconnect(_dt(2))

    assert stats.connects == 1
    assert stats.disconnects == 1
    assert stats.last_reconnect_at == _dt(2)


def test_reset_interval_zeros_only_the_delta() -> None:
    """reset_interval zeros lines_since_write but leaves lines_total intact."""
    stats = FeederStats(started_at=_dt(0))
    stats.record_publish(_dt(5))

    stats.reset_interval()

    assert stats.lines_since_write == 0
    assert stats.lines_total == 1


def test_snapshot_shape() -> None:
    """snapshot returns the expected keys, including delivery metrics."""
    stats = FeederStats(started_at=_dt(0))
    stats.record_connect()
    stats.record_publish(_dt(10))
    stats.record_publish_results(resolved=1, failed=0, last_error=None, now=_dt(10))

    snap = stats.snapshot(_dt(10), in_flight=3)

    assert snap == {
        'started_at': '2026-07-10T18:00:00+00:00',
        'last_publish_at': '2026-07-10T18:00:10+00:00',
        'uptime_seconds': 10,
        'lines_total': 1,
        'lines_last_interval': 1,
        'messages_total': 1,
        'connects': 1,
        'disconnects': 0,
        'last_reconnect_at': None,
        'publishes_resolved': 1,
        'publishes_failed': 0,
        'publishes_in_flight': 3,
        'publishes_dropped': 0,
        'last_failure_at': None,
        'last_failure': None,
    }


def test_record_publish_results_accumulates_and_records_failure() -> None:
    """record_publish_results grows counters and stores last-failure detail."""
    stats = FeederStats(started_at=_dt(0))

    stats.record_publish_results(resolved=5, failed=0, last_error=None, now=_dt(3))
    stats.record_publish_results(resolved=2, failed=1, last_error='boom', now=_dt(4))

    assert stats.publishes_resolved == 7
    assert stats.publishes_failed == 1
    assert stats.last_failure_at == _dt(4)
    assert stats.last_failure == 'boom'


def test_record_publish_results_leaves_failure_detail_none_when_no_failures() -> None:
    """With no failures, last-failure fields stay None."""
    stats = FeederStats(started_at=_dt(0))

    stats.record_publish_results(resolved=4, failed=0, last_error=None, now=_dt(3))

    assert stats.publishes_failed == 0
    assert stats.last_failure_at is None
    assert stats.last_failure is None


def test_record_dropped_accumulates() -> None:
    """record_dropped grows the dropped counter."""
    stats = FeederStats(started_at=_dt(0))

    stats.record_dropped(3)
    stats.record_dropped(2)

    assert stats.publishes_dropped == 5


def test_roll_over_same_day_returns_none() -> None:
    """Within the same UTC day, roll_over_if_new_day does nothing."""
    stats = FeederStats(started_at=_dt_on(10, hour=1))
    stats.record_publish(_dt_on(10, hour=2))

    result = stats.roll_over_if_new_day(_dt_on(10, hour=23), in_flight=0)

    assert result is None
    assert stats.messages_total == 1  # unchanged


def test_roll_over_new_day_captures_then_resets() -> None:
    """Crossing into a new UTC day returns the pre-reset snapshot and zeroes counters."""
    stats = FeederStats(started_at=_dt_on(10, hour=1))
    stats.record_connect()
    stats.record_publish(_dt_on(10, hour=2))
    stats.record_publish_results(resolved=1, failed=0, last_error=None, now=_dt_on(10, hour=2))
    stats.record_dropped(3)

    captured = stats.roll_over_if_new_day(_dt_on(11, hour=0), in_flight=5)

    # The captured dict reflects the day's totals BEFORE reset.
    assert captured is not None
    assert captured['messages_total'] == 1
    assert captured['publishes_resolved'] == 1
    assert captured['publishes_dropped'] == 3
    assert captured['publishes_in_flight'] == 5
    # The seven cumulative counters are now zero.
    assert stats.lines_total == 0
    assert stats.messages_total == 0
    assert stats.connects == 0
    assert stats.disconnects == 0
    assert stats.publishes_resolved == 0
    assert stats.publishes_failed == 0
    assert stats.publishes_dropped == 0
    # The window advanced to the new day.
    assert stats.current_day == date(2026, 7, 11)


def test_roll_over_preserves_non_counter_state() -> None:
    """Rollover leaves started_at, last_* fields, and lines_since_write intact."""
    started = _dt_on(10, hour=1)
    stats = FeederStats(started_at=started)
    stats.record_publish(_dt_on(10, hour=2))  # sets last_publish_at, lines_since_write
    stats.record_disconnect(_dt_on(10, hour=3))  # sets last_reconnect_at
    stats.record_publish_results(resolved=0, failed=1, last_error='boom', now=_dt_on(10, hour=4))

    stats.roll_over_if_new_day(_dt_on(11, hour=0), in_flight=0)

    assert stats.started_at == started
    assert stats.last_publish_at == _dt_on(10, hour=2)
    assert stats.last_reconnect_at == _dt_on(10, hour=3)
    assert stats.last_failure == 'boom'
    assert stats.last_failure_at == _dt_on(10, hour=4)
    assert stats.lines_since_write == 1  # NOT reset by rollover


def test_roll_over_only_first_call_on_new_day_returns_dict() -> None:
    """After a rollover, further same-day calls return None."""
    stats = FeederStats(started_at=_dt_on(10, hour=1))
    stats.record_publish(_dt_on(10, hour=2))

    first = stats.roll_over_if_new_day(_dt_on(11, hour=0), in_flight=0)
    second = stats.roll_over_if_new_day(_dt_on(11, hour=5), in_flight=0)

    assert first is not None
    assert second is None
