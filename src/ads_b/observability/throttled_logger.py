import logging
import time
from collections.abc import Callable


class ThrottledLogger:
    """Log the first N occurrences of each repeating error key, then suppress
    and emit a periodic summary of how many were suppressed.

    Bounds log volume when a single error repeats thousands of times (for
    example a publish backlog failing), while still surfacing the first
    occurrences promptly and reporting the suppressed total on an interval.
    """

    def __init__(
        self,
        logger: logging.Logger,
        sample_count: int,
        summary_interval_seconds: float,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialise the throttle.

        Args:
            logger: The underlying logger to emit through.
            sample_count: Full-detail lines to log per key before suppressing.
            summary_interval_seconds: How often to flush a suppressed-count
                summary per key.
            monotonic: Injectable monotonic clock (defaults to time.monotonic).
        """
        # The wrapped logger and throttle parameters.
        self._logger: logging.Logger = logger
        self._sample_count: int = sample_count
        self._summary_interval_seconds: float = summary_interval_seconds
        self._monotonic: Callable[[], float] = monotonic
        # Per-key state: how many logged this window, how many suppressed, and
        # the monotonic time the current window started.
        self._logged: dict[str, int] = {}
        self._suppressed: dict[str, int] = {}
        self._window_start: dict[str, float] = {}

    def error(self, key: str, message: str) -> None:
        """Log an error, throttled per key.

        The first ``sample_count`` calls for a key log ``message`` at ERROR.
        Further calls are suppressed and counted. Once the summary interval
        elapses, the next call for that key flushes a summary of the suppressed
        count and starts a fresh window.

        Args:
            key: Stable identifier for the error type (groups the throttle).
            message: The full-detail message to log while sampling.
        """
        now: float = self._monotonic()
        # Initialise a key's window the first time it is seen.
        if key not in self._window_start:
            self._window_start[key] = now
            self._logged[key] = 0
            self._suppressed[key] = 0

        # Flush a summary if the interval elapsed and anything was suppressed.
        if (
            now - self._window_start[key] >= self._summary_interval_seconds
            and self._suppressed[key] > 0
        ):
            suppressed: int = self._suppressed[key]
            interval: int = int(self._summary_interval_seconds)
            self._logger.error(
                f"{suppressed:,} more '{key}' errors in the last {interval}s"
            )
            # Start a fresh window: allow full-detail samples again.
            self._window_start[key] = now
            self._logged[key] = 0
            self._suppressed[key] = 0

        # Log at full detail while under the per-window sample budget.
        if self._logged[key] < self._sample_count:
            self._logged[key] += 1
            self._logger.error(message)
        else:
            # Over budget this window: suppress and count.
            self._suppressed[key] += 1
