import logging
import socket
from collections.abc import Callable
from functools import partial

from ads_b.network.open_socket import open_socket
from ads_b.network.sleep_until_stop import sleep_until_stop

logger = logging.getLogger(__name__)

# Multiplier applied to the backoff delay after each failed attempt.
BACKOFF_MULTIPLIER = 2.0
# Granularity of the interruptible backoff sleep, and the worst-case lag before
# a shutdown request is noticed while waiting to reconnect.
BACKOFF_CHUNK_SECONDS = 0.5


def connect_with_backoff(
    host: str,
    port: int,
    timeout_seconds: float,
    initial_backoff_seconds: float,
    max_backoff_seconds: float,
    keepalive_idle_seconds: int,
    keepalive_interval_seconds: int,
    keepalive_max_fails: int,
    should_continue: Callable[[], bool] = lambda: True,
    connect: Callable[..., socket.socket] = open_socket,
    wait: Callable[[float, Callable[[], bool]], None] = partial(
        sleep_until_stop, chunk_seconds=BACKOFF_CHUNK_SECONDS
    ),
) -> socket.socket | None:
    """Connect to the feed, retrying with backoff until successful or stopped.

    Retries forever on OSError with exponential backoff, but polls
    should_continue() before each attempt and during the backoff wait, so a
    shutdown request is honoured promptly even while the feed is down. Returns
    None when asked to stop before a connection is established.

    Args:
        host: Feed host address.
        port: Feed TCP port.
        timeout_seconds: Read timeout to apply to the socket.
        initial_backoff_seconds: Delay before the first retry.
        max_backoff_seconds: Ceiling for the backoff delay.
        keepalive_idle_seconds: Idle time before the first keepalive probe.
        keepalive_interval_seconds: Interval between keepalive probes.
        keepalive_max_fails: Unanswered probes before the connection is dropped.
        should_continue: Returns False to abandon the connect and return None.
        connect: Injectable connect function (defaults to open_socket).
        wait: Injectable interruptible backoff wait (seconds, should_continue).

    Returns:
        A connected, timeout-enabled socket with keepalive applied, or None if a
        shutdown was requested before connecting.
    """
    # Start at the initial delay; grow it after each failure up to the cap.
    backoff: float = initial_backoff_seconds
    while should_continue():
        try:
            # Attempt the connection; return immediately on success.
            sock: socket.socket = connect(
                host,
                port,
                timeout_seconds,
                keepalive_idle_seconds,
                keepalive_interval_seconds,
                keepalive_max_fails,
            )
            logger.info(f'Connected to feed at {host}:{port}')
            return sock
        except OSError as error:
            # Connection failed; log why and how long until the next attempt.
            logger.warning(
                f'Connect to {host}:{port} failed ({error}); retrying in {backoff:.1f}s'
            )
            # Wait out the backoff in small chunks so a stop request is prompt.
            wait(backoff, should_continue)
            # Grow the delay geometrically, but never past the configured cap.
            backoff = min(backoff * BACKOFF_MULTIPLIER, max_backoff_seconds)

    # A shutdown was requested before a connection succeeded.
    return None
