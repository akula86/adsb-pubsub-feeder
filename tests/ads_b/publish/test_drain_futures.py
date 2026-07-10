from concurrent.futures import Future

from ads_b.publish.drain_futures import drain_futures


def test_returns_resolved_count_for_done_futures() -> None:
    """Already-resolved futures drain immediately and count as resolved."""
    done: Future = Future()
    done.set_result('ok')

    result = drain_futures([done], timeout_seconds=1.0)

    assert result.resolved == 1
    assert result.failed == 0
    assert result.still_pending == []


def test_bounded_wait_reports_unresolved_as_still_pending(caplog) -> None:
    """An unresolved future does not hang; it is returned as still_pending."""
    never: Future = Future()

    with caplog.at_level('WARNING'):
        result = drain_futures([never], timeout_seconds=0.05)

    # The unresolved future is reported, not blocked on forever.
    assert result.still_pending == [never]
    assert result.resolved == 0
    assert 'did not complete' in caplog.text


def test_counts_failed_future_without_logging(caplog) -> None:
    """A drained failed future is counted/reported but not logged here."""
    failed: Future = Future()
    failed.set_exception(RuntimeError('drain boom'))

    with caplog.at_level('ERROR'):
        result = drain_futures([failed], timeout_seconds=1.0)

    assert result.failed == 1
    assert result.last_error == 'drain boom'
    assert 'drain boom' not in caplog.text
