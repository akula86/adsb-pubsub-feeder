import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


def sleep_until_stop(
    total_seconds: float,
    should_continue: Callable[[], bool],
    chunk_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    """Sleep up to total_seconds, in chunk_seconds increments, stopping early.

    Between each chunk it checks should_continue(); when that returns False the
    sleep ends immediately. This bounds how long a caller stays blocked to about
    one chunk, so a shutdown request is honoured promptly even during a long
    wait. The final chunk is clamped so the total sleep never overshoots.

    Args:
        total_seconds: Maximum time to sleep.
        chunk_seconds: Granularity of each sleep step (and the worst-case lag
            before a stop request is noticed).
        should_continue: Returns False to end the sleep early.
        sleep: Injectable sleep function (defaults to time.sleep).
        monotonic: Injectable monotonic clock (defaults to time.monotonic).
    """
    # Absolute deadline for the whole sleep.
    deadline: float = monotonic() + total_seconds
    while should_continue():
        # Stop once the deadline has passed.
        remaining: float = deadline - monotonic()
        if remaining <= 0:
            return
        # Sleep one chunk, but never past the remaining time.
        sleep(min(chunk_seconds, remaining))
