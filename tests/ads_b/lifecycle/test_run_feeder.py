import json
from datetime import datetime, timezone
from concurrent.futures import Future
from pathlib import Path

from ads_b.config.config_model import Config
from ads_b.publish.publish_line import publish_line
from ads_b.lifecycle.run_feeder import run_feeder


def _fixed_now() -> datetime:
    """Return a fixed UTC time for tests that do not care about wall clock."""
    return datetime(2026, 7, 10, 18, 0, 0, tzinfo=timezone.utc)


class _Closeable:
    """A fake socket exposing a no-op close() for run_feeder to call."""

    def close(self) -> None:
        """Do nothing; the fake socket needs no teardown."""


def _config() -> Config:
    """Build a Config with small values suitable for tests."""
    return Config(
        feed_host='h',
        feed_port=30_003,
        project_id='p',
        topic_id='t',
        location='SJC',
        initial_backoff_seconds=1.0,
        max_backoff_seconds=30.0,
        feed_idle_timeout_seconds=60.0,
        keepalive_idle_seconds=1,
        keepalive_interval_seconds=3,
        keepalive_max_fails=5,
        health_file_path='/tmp/unused.json',
        write_interval_seconds=300.0,
        health_tick_seconds=1.0,
        health_log_file_path='/tmp/unused-history.log',
        health_log_max_megabytes=5,
        health_log_backup_count=3,
        log_file_path='/tmp/unused.log',
        log_max_megabytes=5,
        log_backup_count=3,
        max_pending=1_000,
        error_sample_count=5,
        error_summary_interval_seconds=60.0,
        credentials_path='/dev/null',
    )


class RecordingPublisher:
    """A publisher whose publish() records each message's bytes and attributes."""

    def __init__(self) -> None:
        """Initialise the recorded-message and recorded-attribute lists."""
        self.published: list[bytes] = []
        self.attrs: list[dict[str, str]] = []

    def publish(self, _topic: str, data: bytes, **attrs: str) -> Future:
        """Record the published bytes and attributes, return a completed future."""
        self.published.append(data)
        self.attrs.append(attrs)
        future: Future = Future()
        future.set_result('msg-id')
        return future


class FailingPublisher:
    """A publisher whose every publish future completes with an exception."""

    def publish(self, _topic: str, _data: bytes, **_attrs: str) -> Future:
        """Return a future already failed with a RuntimeError."""
        future: Future = Future()
        future.set_exception(RuntimeError('delivery boom'))
        return future


def test_publishes_one_message_per_line(tmp_path: Path) -> None:
    """Each read line is published as its own message; then shutdown."""
    publisher = RecordingPublisher()
    continues = iter([True, True, True, True])
    cfg = Config(**{**_config().__dict__, 'health_file_path': str(tmp_path / 'h.json')})

    def fake_connect(*_args: object, **_kwargs: object) -> _Closeable:
        return _Closeable()

    def fake_read(_sock: object, _idle: float, _monotonic: object):
        yield 'L1'
        yield 'L2'
        yield 'L3'

    run_feeder(
        cfg,
        publisher,
        'projects/p/topics/t',
        connect=fake_connect,
        read_lines=fake_read,
        publish=publish_line,
        should_continue=lambda: next(continues),
        now=_fixed_now,
        drain_timeout_seconds=0.05,
    )

    # Three lines produce three individual messages, in order.
    assert publisher.published == [b'L1', b'L2', b'L3']
    # Every message carries the configured location as a LOCATION attribute,
    # proving config.location is threaded through to the publish call.
    assert publisher.attrs == [{'LOCATION': 'SJC'}] * 3


def test_health_file_written_on_shutdown(tmp_path: Path) -> None:
    """A health file is written when the feeder stops, with line/message stats."""
    publisher = RecordingPublisher()
    health_path = tmp_path / 'health.json'
    continues = iter([True, True, False])

    def fake_connect(*_args: object, **_kwargs: object) -> _Closeable:
        return _Closeable()

    def fake_read(_sock: object, _idle: float, _monotonic: object):
        yield 'ONLY'

    cfg = _config()
    cfg_with_path = Config(**{**cfg.__dict__, 'health_file_path': str(health_path)})

    run_feeder(
        cfg_with_path,
        publisher,
        'projects/p/topics/t',
        connect=fake_connect,
        read_lines=fake_read,
        publish=publish_line,
        should_continue=lambda: next(continues),
        now=_fixed_now,
        drain_timeout_seconds=0.05,
    )

    data = json.loads(health_path.read_text())
    assert data['lines_total'] == 1
    assert data['messages_total'] == 1
    assert data['connects'] == 1


def test_health_write_failure_is_swallowed(tmp_path: Path) -> None:
    """A failing health write does not stop the feeder."""
    publisher = RecordingPublisher()
    bad_path = str(tmp_path / 'no_such_dir' / 'health.json')
    continues = iter([True, True, False])

    def fake_connect(*_args: object, **_kwargs: object) -> _Closeable:
        return _Closeable()

    def fake_read(_sock: object, _idle: float, _monotonic: object):
        yield 'ONLY'

    cfg = _config()
    cfg_bad = Config(**{**cfg.__dict__, 'health_file_path': bad_path})

    # Completes without raising despite the un-writable health path.
    run_feeder(
        cfg_bad,
        publisher,
        'projects/p/topics/t',
        connect=fake_connect,
        read_lines=fake_read,
        publish=publish_line,
        should_continue=lambda: next(continues),
        now=_fixed_now,
        drain_timeout_seconds=0.05,
    )

    assert publisher.published == [b'ONLY']


def test_reconnects_after_connection_error(tmp_path: Path) -> None:
    """A ConnectionError from the reader triggers a reconnect and continues."""
    publisher = RecordingPublisher()
    connect_count = {'n': 0}

    def fake_connect(*_args: object, **_kwargs: object) -> _Closeable:
        connect_count['n'] += 1
        return _Closeable()

    def fake_read(_sock: object, _idle: float, _monotonic: object):
        yield 'AFTER-DROP'
        raise ConnectionError('dropped')

    continues = iter([True, True, False, False])
    cfg = Config(**{**_config().__dict__, 'health_file_path': str(tmp_path / 'h.json')})

    run_feeder(
        cfg,
        publisher,
        'projects/p/topics/t',
        connect=fake_connect,
        read_lines=fake_read,
        publish=publish_line,
        should_continue=lambda: next(continues),
        now=_fixed_now,
        drain_timeout_seconds=0.05,
    )

    assert connect_count['n'] >= 2
    assert publisher.published == [b'AFTER-DROP']


def _advancing_monotonic(first: float, rest: float) -> object:
    """Return a zero-arg callable yielding ``first`` once, then ``rest`` forever.

    Args:
        first: The value returned on the first call (models ``last_health_write``
            initialisation before the read loop starts).
        rest: The value returned on every subsequent call.

    Returns:
        A callable with no arguments suitable for injection as ``monotonic``.
    """
    calls = {'n': 0}

    def _monotonic() -> float:
        """Return the next monotonic value, advancing past the first call."""
        calls['n'] += 1
        return first if calls['n'] == 1 else rest

    return _monotonic


def test_health_file_written_on_interval(tmp_path: Path) -> None:
    """The periodic in-loop health write fires once the interval elapses."""
    publisher = RecordingPublisher()
    health_path = tmp_path / 'health.json'
    continues = iter([True, True, False])
    cfg = Config(**{**_config().__dict__, 'health_file_path': str(health_path)})

    def fake_connect(*_args: object, **_kwargs: object) -> _Closeable:
        return _Closeable()

    def fake_read(_sock: object, _idle: float, _monotonic: object):
        yield 'ONLY'

    # First call initialises last_health_write to 0.0; every call after that
    # (the deadline check, and the reset if it fires) returns 500.0, so the
    # first read event's deadline check (500.0 - 0.0 = 500.0 >= 300.0) fires
    # the periodic write from inside the read loop, not at shutdown.
    monotonic = _advancing_monotonic(first=0.0, rest=500.0)

    run_feeder(
        cfg,
        publisher,
        'projects/p/topics/t',
        connect=fake_connect,
        read_lines=fake_read,
        publish=publish_line,
        should_continue=lambda: next(continues),
        monotonic=monotonic,
        now=_fixed_now,
        drain_timeout_seconds=0.05,
    )

    # The periodic branch wrote a valid health file with the one line seen so far.
    data = json.loads(health_path.read_text())
    assert data['lines_total'] == 1
    assert data['messages_total'] == 1


def test_idle_tick_publishes_nothing(tmp_path: Path) -> None:
    """A None idle tick from the reader does not publish a message."""
    publisher = RecordingPublisher()
    continues = iter([True, True, False])
    cfg = Config(**{**_config().__dict__, 'health_file_path': str(tmp_path / 'h.json')})

    def fake_connect(*_args: object, **_kwargs: object) -> _Closeable:
        return _Closeable()

    def fake_read(_sock: object, _idle: float, _monotonic: object):
        yield None

    run_feeder(
        cfg,
        publisher,
        'projects/p/topics/t',
        connect=fake_connect,
        read_lines=fake_read,
        publish=publish_line,
        should_continue=lambda: next(continues),
        now=_fixed_now,
        drain_timeout_seconds=0.05,
    )

    # An idle tick alone publishes nothing.
    assert publisher.published == []


def test_stops_when_connect_returns_none(tmp_path: Path) -> None:
    """A None from connect (shutdown during backoff) ends the loop cleanly."""
    publisher = RecordingPublisher()
    health_path = tmp_path / 'health.json'
    cfg = Config(**{**_config().__dict__, 'health_file_path': str(health_path)})
    read_called = {'n': 0}

    def fake_connect(*_args: object, **_kwargs: object) -> None:
        # connect abandoned the attempt because a shutdown was requested.
        return None

    def fake_read(_sock: object, _idle: float, _monotonic: object):
        # Must never be called: there is no socket to read from.
        read_called['n'] += 1
        yield 'SHOULD-NOT-HAPPEN'

    run_feeder(
        cfg,
        publisher,
        'projects/p/topics/t',
        connect=fake_connect,
        read_lines=fake_read,
        publish=publish_line,
        should_continue=lambda: True,
        now=_fixed_now,
        drain_timeout_seconds=0.05,
    )

    # No read, no publish; the loop exited on the None, and the final health
    # file was still written on the way out.
    assert read_called['n'] == 0
    assert publisher.published == []
    assert health_path.exists()


class NeverResolvingPublisher:
    """A publisher whose publish() returns futures that never resolve."""

    def publish(self, _topic: str, _data: bytes, **_attrs: str) -> Future:
        """Return a Future with no result set, so it stays pending forever."""
        return Future()


def test_drops_oldest_when_backlog_full(tmp_path: Path) -> None:
    """When pending is full of unresolved futures, the oldest is dropped."""
    publisher = NeverResolvingPublisher()
    health_path = tmp_path / 'h.json'
    cfg = Config(
        **{
            **_config().__dict__,
            'max_pending': 2,
            'health_file_path': str(health_path),
        }
    )
    continues = iter([True, True, True, True, False])

    def fake_connect(*_args: object, **_kwargs: object) -> _Closeable:
        return _Closeable()

    def fake_read(_sock: object, _idle: float, _monotonic: object):
        for _ in range(4):
            yield 'MSG,line'

    run_feeder(
        cfg,
        publisher,
        'projects/p/topics/t',
        connect=fake_connect,
        read_lines=fake_read,
        publish=publish_line,
        should_continue=lambda: next(continues),
        now=_fixed_now,
        drain_timeout_seconds=0.05,
    )

    # 4 lines with a cap of 2 -> at least 2 dropped, and in_flight never exceeded 2.
    data = json.loads(health_path.read_text())
    assert data['publishes_dropped'] >= 2
    assert data['publishes_in_flight'] <= 2


def test_crosses_utc_midnight_logs_and_resets(tmp_path: Path, caplog) -> None:
    """Crossing UTC midnight logs a daily-totals line and zeroes the counters."""
    publisher = RecordingPublisher()
    health_path = tmp_path / 'h.json'
    continues = iter([True, True, False])
    cfg = Config(**{**_config().__dict__, 'health_file_path': str(health_path)})

    def fake_connect(*_args: object, **_kwargs: object) -> _Closeable:
        return _Closeable()

    def fake_read(_sock: object, _idle: float, _monotonic: object):
        yield 'FIRST'
        yield 'SECOND'

    # A stepping clock: the first read event lands just before UTC midnight on
    # day 10 (started_at, so current_day starts at day 10); the second read
    # event lands just after midnight on day 11, triggering the rollover. Extra
    # values cover the remaining now() calls (reconcile, drain, shutdown write)
    # and the fallback holds the last (day-11) value once exhausted.
    times = iter(
        [
            datetime(2026, 7, 10, 23, 59, 59, tzinfo=timezone.utc),  # started_at
            datetime(2026, 7, 10, 23, 59, 59, tzinfo=timezone.utc),  # record_publish 1
            datetime(2026, 7, 10, 23, 59, 59, tzinfo=timezone.utc),  # reconcile 1
            datetime(2026, 7, 10, 23, 59, 59, tzinfo=timezone.utc),  # rollover check 1
            datetime(2026, 7, 11, 0, 0, 1, tzinfo=timezone.utc),  # record_publish 2
            datetime(2026, 7, 11, 0, 0, 1, tzinfo=timezone.utc),  # reconcile 2
            datetime(2026, 7, 11, 0, 0, 1, tzinfo=timezone.utc),  # rollover check 2
        ]
    )
    last = {'t': datetime(2026, 7, 11, 0, 0, 9, tzinfo=timezone.utc)}

    def stepping_now() -> datetime:
        """Advance through the queued times, then hold the final value."""
        try:
            last['t'] = next(times)
        except StopIteration:
            pass
        return last['t']

    with caplog.at_level('INFO'):
        run_feeder(
            cfg,
            publisher,
            'projects/p/topics/t',
            connect=fake_connect,
            read_lines=fake_read,
            publish=publish_line,
            should_continue=lambda: next(continues),
            now=stepping_now,
            drain_timeout_seconds=0.05,
        )

    # The daily-totals line was logged at the midnight boundary.
    assert 'Daily totals at UTC midnight' in caplog.text
    # After rollover the final health file shows reset cumulative counters.
    data = json.loads(health_path.read_text())
    assert data['messages_total'] == 0


def test_failed_publishes_appear_in_health_file(tmp_path: Path) -> None:
    """A failing publish surfaces publishes_failed and last_failure in health."""
    publisher = FailingPublisher()
    health_path = tmp_path / 'health.json'
    continues = iter([True, True, False])
    cfg = Config(**{**_config().__dict__, 'health_file_path': str(health_path)})

    def fake_connect(*_args: object, **_kwargs: object) -> _Closeable:
        return _Closeable()

    def fake_read(_sock: object, _idle: float, _monotonic: object):
        yield 'ONLY'

    run_feeder(
        cfg,
        publisher,
        'projects/p/topics/t',
        connect=fake_connect,
        read_lines=fake_read,
        publish=publish_line,
        should_continue=lambda: next(continues),
        now=_fixed_now,
        drain_timeout_seconds=0.05,
    )

    data = json.loads(health_path.read_text())
    assert data['publishes_failed'] >= 1
    assert data['last_failure'] == 'delivery boom'
    assert data['publishes_in_flight'] == 0
