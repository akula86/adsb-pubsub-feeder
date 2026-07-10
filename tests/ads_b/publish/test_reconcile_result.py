from concurrent.futures import Future

from ads_b.publish.reconcile_result import ReconcileResult


def test_holds_outcome_fields() -> None:
    """ReconcileResult carries the pending list and outcome counts."""
    pending: Future = Future()

    result = ReconcileResult(
        still_pending=[pending], resolved=3, failed=1, last_error='boom'
    )

    assert result.still_pending == [pending]
    assert result.resolved == 3
    assert result.failed == 1
    assert result.last_error == 'boom'
