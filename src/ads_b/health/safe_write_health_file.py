import logging
from datetime import datetime

from ads_b.health.feeder_stats import FeederStats
from ads_b.health.write_health_file import write_health_file
from ads_b.observability.throttled_logger import ThrottledLogger

logger = logging.getLogger(__name__)


def safe_write_health_file(
    path: str,
    stats: FeederStats,
    now: datetime,
    write_interval_seconds: float,
    in_flight: int,
    throttle: ThrottledLogger,
) -> None:
    """Write the health file, logging and swallowing any OSError.

    A health-file write must never stop the feeder, so an OS-level failure
    (permissions, disk full, missing directory) is logged through the throttle
    and suppressed rather than propagated.

    Args:
        path: Destination health file path.
        stats: The feeder stats to snapshot.
        now: Current time for uptime and the status check.
        write_interval_seconds: The configured write interval, for staleness.
        in_flight: Publish futures submitted but not yet reconciled.
        throttle: Throttled logger for the flood-prone write-failure error.
    """
    # Contain OS-level write failures so the read loop is never interrupted.
    try:
        write_health_file(path, stats, now, write_interval_seconds, in_flight)
    except OSError as error:
        throttle.error('health_write_failed', f'Health file write failed: {error}')
