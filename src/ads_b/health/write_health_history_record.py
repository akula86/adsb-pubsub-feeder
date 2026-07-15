import json
import logging

from ads_b.observability.throttled_logger import ThrottledLogger


def write_health_history_record(
    record: dict,
    history_logger: logging.Logger,
    throttle: ThrottledLogger,
) -> None:
    """Emit one health-history record as a JSON line, swallowing OSError.

    Writing history must never stop the feeder, so a filesystem failure during
    the underlying rotating-file write is logged through the throttle and
    suppressed rather than propagated.

    Args:
        record: The JSON-serialisable record to emit.
        history_logger: The dedicated health-history logger.
        throttle: Throttled logger for the flood-prone write-failure error.
    """
    # Serialise once and emit as a single line; contain OS-level write failures
    # so the read loop is never interrupted by a full or unwritable disk.
    try:
        history_logger.info(json.dumps(record))
    except OSError as error:
        throttle.error(
            'health_history_write_failed',
            f'Health-history write failed: {error}',
        )
