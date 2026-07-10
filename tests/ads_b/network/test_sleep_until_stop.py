from collections.abc import Callable

from ads_b.network.sleep_until_stop import sleep_until_stop


def _clock(times: list[float]) -> Callable[[], float]:
    """Return a monotonic() stub yielding the given values in order."""
    iterator = iter(times)
    return lambda: next(iterator)


def test_sleeps_full_duration_when_not_stopped() -> None:
    """With should_continue always True, it sleeps the whole duration in chunks."""
    sleeps: list[float] = []
    # monotonic() is read once at start, then before each chunk check.
    clock = _clock([0.0, 0.0, 0.5, 1.0, 1.5, 2.0])

    sleep_until_stop(
        total_seconds=2.0,
        chunk_seconds=0.5,
        should_continue=lambda: True,
        sleep=sleeps.append,
        monotonic=clock,
    )

    # Four 0.5s chunks make up the 2.0s total.
    assert sleeps == [0.5, 0.5, 0.5, 0.5]


def test_returns_early_when_stopped() -> None:
    """It stops sleeping as soon as should_continue turns False."""
    sleeps: list[float] = []
    # Flip should_continue to False after the first chunk.
    calls = {'n': 0}

    def should_continue() -> bool:
        calls['n'] += 1
        return calls['n'] <= 1

    clock = _clock([0.0, 0.0, 0.5, 1.0])

    sleep_until_stop(
        total_seconds=10.0,
        chunk_seconds=0.5,
        should_continue=should_continue,
        sleep=sleeps.append,
        monotonic=clock,
    )

    # Only one chunk slept before the flag flipped; not the full 10s.
    assert sleeps == [0.5]


def test_final_chunk_is_clamped_to_remaining() -> None:
    """The last chunk is shortened so total sleep never overshoots the duration."""
    sleeps: list[float] = []
    clock = _clock([0.0, 0.0, 0.4, 0.7])

    sleep_until_stop(
        total_seconds=0.7,
        chunk_seconds=0.4,
        should_continue=lambda: True,
        sleep=sleeps.append,
        monotonic=clock,
    )

    # 0.4 then the clamped remainder (~0.3), summing to 0.7 with no overshoot.
    assert len(sleeps) == 2
    assert sleeps[0] == 0.4
    assert abs(sleeps[1] - 0.3) < 1e-9
    assert sum(sleeps) <= 0.7 + 1e-9
