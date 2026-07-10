import logging
import socket

from ads_b.network.apply_keepalive import apply_keepalive

logger = logging.getLogger(__name__)


def open_socket(
    host: str,
    port: int,
    timeout_seconds: float,
    keepalive_idle_seconds: int,
    keepalive_interval_seconds: int,
    keepalive_max_fails: int,
) -> socket.socket:
    """Open a TCP socket to host:port, apply a read timeout, and enable keepalive.

    Args:
        host: Feed host address.
        port: Feed TCP port.
        timeout_seconds: Read timeout to set on the socket.
        keepalive_idle_seconds: Idle time before the first keepalive probe.
        keepalive_interval_seconds: Interval between keepalive probes.
        keepalive_max_fails: Unanswered probes before the connection is dropped.

    Returns:
        A connected socket with the read timeout and keepalive applied.
    """
    # Open the TCP connection to the feed endpoint.
    sock: socket.socket = socket.create_connection((host, port))
    # Apply the read timeout so later recv() calls return control periodically.
    sock.settimeout(timeout_seconds)
    # Enable TCP keepalive so a dead peer is detected at the OS layer.
    apply_keepalive(
        sock,
        keepalive_idle_seconds,
        keepalive_interval_seconds,
        keepalive_max_fails,
    )
    return sock
