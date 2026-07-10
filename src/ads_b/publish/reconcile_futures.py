import logging
from concurrent.futures import Future

from ads_b.publish.reconcile_result import ReconcileResult

logger = logging.getLogger(__name__)


def reconcile_futures(pending: list[Future]) -> ReconcileResult:
    """Check completed publish futures, drop the done ones, and report outcomes.

    Args:
        pending: Publish futures that have not yet been reconciled.

    Returns:
        A ReconcileResult with the still-pending futures and outcome counts.
    """
    # Accumulate outcomes while partitioning done from still-running futures.
    still_pending: list[Future] = []
    resolved: int = 0
    failed: int = 0
    last_error: str | None = None
    for future in pending:
        # A future that is not done stays pending, unblocked.
        if not future.done():
            still_pending.append(future)
            continue
        # A finished future either succeeded or carries a publish exception.
        error: BaseException | None = future.exception()
        if error is not None:
            failed += 1
            last_error = str(error)
        else:
            resolved += 1
    return ReconcileResult(
        still_pending=still_pending,
        resolved=resolved,
        failed=failed,
        last_error=last_error,
    )
