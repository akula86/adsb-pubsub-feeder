import socket
from collections.abc import Callable

from ads_b.network.connect_with_backoff import connect_with_backoff


def test_connects_on_first_try_no_wait() -> None:
    """A successful first connect returns the socket and never waits."""
    sentinel = socket.socket()
    waits: list[float] = []
    connect_calls: list[tuple] = []

    def fake_connect(host, port, timeout, idle, interval, fails) -> socket.socket:
        connect_calls.append((host, port, timeout, idle, interval, fails))
        return sentinel

    def fake_wait(seconds: float, _should_continue: Callable[[], bool]) -> None:
        waits.append(seconds)

    result = connect_with_backoff(
        'host', 30_003, 5.0, 1.0, 30.0, 1, 3, 5,
        connect=fake_connect, wait=fake_wait,
    )

    assert result is sentinel
    assert waits == []
    assert connect_calls == [('host', 30_003, 5.0, 1, 3, 5)]
    sentinel.close()


def test_retries_with_exponential_backoff_then_succeeds() -> None:
    """Failed connects retry with doubling backoff capped at max_backoff_seconds."""
    sentinel = socket.socket()
    waits: list[float] = []
    attempts = {'n': 0}

    def flaky_connect(host, port, timeout, idle, interval, fails) -> socket.socket:
        # Fail the first three attempts, succeed on the fourth.
        attempts['n'] += 1
        if attempts['n'] < 4:
            raise OSError('connection refused')
        return sentinel

    def fake_wait(seconds: float, _should_continue: Callable[[], bool]) -> None:
        waits.append(seconds)

    result = connect_with_backoff(
        'host', 30_003, 5.0, 1.0, 4.0, 1, 3, 5,
        connect=flaky_connect, wait=fake_wait,
    )

    assert result is sentinel
    # 1.0 -> 2.0 -> 4.0 (capped at max 4.0), one wait before each retry.
    assert waits == [1.0, 2.0, 4.0]
    sentinel.close()


def test_returns_none_when_stopped_before_first_attempt() -> None:
    """If should_continue is already False, it returns None without connecting."""
    connect_calls: list[tuple] = []

    def fake_connect(*args) -> socket.socket:
        connect_calls.append(args)
        return socket.socket()

    result = connect_with_backoff(
        'host', 30_003, 5.0, 1.0, 30.0, 1, 3, 5,
        should_continue=lambda: False,
        connect=fake_connect,
        wait=lambda _s, _c: None,
    )

    # No connection attempted, and None signals the caller to stop.
    assert result is None
    assert connect_calls == []


def test_returns_none_when_stopped_during_backoff() -> None:
    """A shutdown request during the retry loop ends it with None."""
    # Fail the connect so the loop enters backoff; stop after the first failure.
    calls = {'continue': [True, False]}

    def failing_connect(*_args) -> socket.socket:
        raise OSError('down')

    def should_continue() -> bool:
        return calls['continue'].pop(0)

    result = connect_with_backoff(
        'host', 30_003, 5.0, 1.0, 30.0, 1, 3, 5,
        should_continue=should_continue,
        connect=failing_connect,
        wait=lambda _s, _c: None,
    )

    assert result is None


def test_default_wait_is_callable() -> None:
    """The default wait (a partial of sleep_until_stop) invokes cleanly.

    The other tests inject a fake wait, so this one exercises the real default
    to catch a broken partial binding. It fails the connect once, then stops
    during the (real) backoff so the loop ends without a long real sleep.
    """
    # Calls, in order: outer-loop guard (True → attempt), the real
    # sleep_until_stop's own guard during backoff (False → returns at once),
    # then the outer-loop guard again (False → exit with None).
    calls = {'continue': [True, False, False]}

    def failing_connect(*_args) -> socket.socket:
        raise OSError('down')

    def should_continue() -> bool:
        return calls['continue'].pop(0)

    # Note: no wait= override — the real partial(sleep_until_stop, chunk=...) runs.
    result = connect_with_backoff(
        'host', 30_003, 5.0, 1.0, 30.0, 1, 3, 5,
        should_continue=should_continue,
        connect=failing_connect,
    )

    assert result is None
