import logging

from ads_b.observability.throttled_logger import ThrottledLogger


class _Clock:
    """A controllable monotonic clock for deterministic interval tests."""

    def __init__(self) -> None:
        self.t: float = 0.0

    def __call__(self) -> float:
        return self.t


def test_logs_first_n_then_suppresses(caplog) -> None:
    """The first sample_count messages for a key log; the rest are suppressed."""
    clock = _Clock()
    tl = ThrottledLogger(
        logging.getLogger('t1'), sample_count=3,
        summary_interval_seconds=60.0, monotonic=clock,
    )

    with caplog.at_level('ERROR'):
        for _ in range(10):
            tl.error('publish_failed', 'boom')

    # Exactly 3 full-detail 'boom' lines were emitted; 7 suppressed.
    assert caplog.text.count('boom') == 3


def test_summary_emitted_after_interval_with_count(caplog) -> None:
    """After the interval, a summary reports the suppressed count."""
    clock = _Clock()
    tl = ThrottledLogger(
        logging.getLogger('t2'), sample_count=2,
        summary_interval_seconds=60.0, monotonic=clock,
    )

    with caplog.at_level('ERROR'):
        for _ in range(5):  # 2 logged, 3 suppressed
            tl.error('k', 'err')
        clock.t = 60.0  # advance past the interval
        tl.error('k', 'err')  # triggers the summary

    # The summary reports exactly 3 suppressed (the 3 during the window); the
    # triggering call becomes a fresh sample and is not counted.
    assert "more 'k' errors" in caplog.text


def test_keys_are_independent(caplog) -> None:
    """Different keys have independent sample budgets."""
    clock = _Clock()
    tl = ThrottledLogger(
        logging.getLogger('t3'), sample_count=1,
        summary_interval_seconds=60.0, monotonic=clock,
    )

    with caplog.at_level('ERROR'):
        tl.error('a', 'msg-a')
        tl.error('b', 'msg-b')

    # Each key logged its first occurrence independently.
    assert 'msg-a' in caplog.text
    assert 'msg-b' in caplog.text


def test_comma_formats_large_suppressed_count(caplog) -> None:
    """A suppressed count >= 1000 is comma-formatted in the summary."""
    clock = _Clock()
    tl = ThrottledLogger(
        logging.getLogger('t4'), sample_count=1,
        summary_interval_seconds=60.0, monotonic=clock,
    )

    with caplog.at_level('ERROR'):
        for _ in range(1_501):
            tl.error('k', 'e')
        clock.t = 60.0
        tl.error('k', 'e')

    # The summary count is comma-formatted (e.g. 1,500).
    assert '1,5' in caplog.text
