from concurrent.futures import Future
from dataclasses import dataclass


@dataclass(frozen=True)
class ReconcileResult:
    """Outcome of inspecting a batch of publish futures.

    Attributes:
        still_pending: Futures not yet completed (kept for further tracking).
        resolved: Count that completed successfully.
        failed: Count that completed with an exception.
        last_error: str() of the most recent failure, or None if none failed.
    """

    still_pending: list[Future]
    resolved: int
    failed: int
    last_error: str | None
