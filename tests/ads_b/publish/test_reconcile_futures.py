from concurrent.futures import Future

from ads_b.publish.reconcile_futures import reconcile_futures


def test_keeps_pending_drops_done_and_counts_resolved() -> None:
    """Unfinished futures are retained; finished ok ones are counted resolved."""
    done: Future = Future()
    done.set_result('ok')
    pending: Future = Future()

    result = reconcile_futures([done, pending])

    # Only the still-running future survives; the done one counts as resolved.
    assert result.still_pending == [pending]
    assert result.resolved == 1
    assert result.failed == 0
    assert result.last_error is None


def test_counts_failed_future_without_logging(caplog) -> None:
    """A finished failed future is counted and reported, but not logged here."""
    failed: Future = Future()
    failed.set_exception(RuntimeError('publish boom'))

    with caplog.at_level('ERROR'):
        result = reconcile_futures([failed])

    # The failed future is dropped and counted; the error surfaces via the return.
    assert result.still_pending == []
    assert result.resolved == 0
    assert result.failed == 1
    assert result.last_error == 'publish boom'
    # The failure is reported via the return value, not the log.
    assert 'publish boom' not in caplog.text


def test_last_error_is_the_last_failure_in_order() -> None:
    """When several futures fail, last_error is the last one in iteration order."""
    first: Future = Future()
    first.set_exception(RuntimeError('first boom'))
    second: Future = Future()
    second.set_exception(RuntimeError('second boom'))

    result = reconcile_futures([first, second])

    assert result.failed == 2
    assert result.last_error == 'second boom'


def test_empty_input_yields_zeros() -> None:
    """No futures means empty pending and zero counts."""
    result = reconcile_futures([])

    assert result.still_pending == []
    assert result.resolved == 0
    assert result.failed == 0
    assert result.last_error is None
