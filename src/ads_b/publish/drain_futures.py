import logging
from concurrent.futures import Future, wait

from ads_b.publish.reconcile_result import ReconcileResult

logger = logging.getLogger(__name__)


def drain_futures(pending: list[Future], timeout_seconds: float) -> ReconcileResult:
    """Block until pending publish futures complete or the timeout elapses.

    Bounding the wait ensures a wedged publish (e.g. broker unreachable at
    shutdown) cannot hang the process past a service manager's stop timeout.

    Args:
        pending: Publish futures to wait on before shutdown.
        timeout_seconds: Maximum total time to wait for all futures.

    Returns:
        A ReconcileResult: still_pending holds the futures unresolved at the
        deadline; resolved/failed/last_error describe the ones that finished.
    """
    # Wait for all futures, but no longer than the shutdown budget.
    done, not_done = wait(pending, timeout=timeout_seconds)

    # Tally outcomes for the futures that finished.
    resolved: int = 0
    failed: int = 0
    last_error: str | None = None
    for future in done:
        error: BaseException | None = future.exception()
        if error is not None:
            failed += 1
            last_error = str(error)
        else:
            resolved += 1

    # Report any futures still unresolved so a stuck publish is not silent.
    if not_done:
        logger.warning(
            f'{len(not_done)} publish(es) did not complete within '
            f'{timeout_seconds:.1f}s of shutdown'
        )

    return ReconcileResult(
        still_pending=list(not_done),
        resolved=resolved,
        failed=failed,
        last_error=last_error,
    )
