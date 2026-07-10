import json
import logging
import os
import tempfile
from datetime import datetime

from ads_b.health.feeder_stats import FeederStats

logger = logging.getLogger(__name__)

# A publish within this multiple of the write interval counts as healthy.
HEALTHY_INTERVAL_MULTIPLIER = 2.0


def write_health_file(
    path: str,
    stats: FeederStats,
    now: datetime,
    write_interval_seconds: float,
    in_flight: int,
) -> None:
    """Write the current stats as JSON to path, atomically, then reset the delta.

    Args:
        path: Destination health file path (overwritten each call).
        stats: The feeder stats to snapshot.
        now: Current time, used for uptime and the status check.
        write_interval_seconds: The configured write interval, used for staleness.
        in_flight: Publish futures submitted but not yet reconciled.
    """
    # Build the payload and derive the healthy/stale status from publish recency.
    payload: dict = stats.snapshot(now, in_flight)
    healthy_window: float = HEALTHY_INTERVAL_MULTIPLIER * write_interval_seconds
    is_healthy: bool = (
        stats.last_publish_at is not None
        and (now - stats.last_publish_at).total_seconds() <= healthy_window
    )
    # Put status first for readability; dicts preserve insertion order.
    ordered: dict = {'status': 'healthy' if is_healthy else 'stale', **payload}

    # Serialize to a temp file in the same directory, then atomically rename.
    directory: str = os.path.dirname(path) or '.'
    fd, temp_path = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        # Write the JSON body and flush to the OS before the rename.
        with os.fdopen(fd, 'w') as handle:
            json.dump(ordered, handle, indent=2)
        # Atomic replace: readers see either the old file or the new one.
        os.replace(temp_path, path)
    except OSError:
        # Clean up the temp file on failure, then re-raise for the caller to log.
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    # The interval delta has been written out; start the next interval fresh.
    stats.reset_interval()
