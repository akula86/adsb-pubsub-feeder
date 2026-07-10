import logging
import socket

logger = logging.getLogger(__name__)


def apply_keepalive(
    sock: socket.socket,
    idle_seconds: int,
    interval_seconds: int,
    max_fails: int,
) -> None:
    """Enable TCP keepalive on a socket and set its idle, interval, and count.

    After idle_seconds of silence the OS sends a keepalive probe, repeats every
    interval_seconds, and drops the connection after max_fails unanswered probes.
    Each per-option setting is applied only if the running platform exposes the
    matching socket constant, so this works on both Linux (TCP_KEEPIDLE) and
    macOS/BSD (TCP_KEEPALIVE). SO_KEEPALIVE exists everywhere and is always set.

    Args:
        sock: The connected socket to configure.
        idle_seconds: Idle time before the first keepalive probe.
        interval_seconds: Interval between probes.
        max_fails: Unanswered probes before the connection is dropped.
    """
    # Turn keepalive on at the socket level; this constant exists on all platforms.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    # Idle-before-first-probe: Linux calls it TCP_KEEPIDLE, macOS/BSD TCP_KEEPALIVE.
    if hasattr(socket, 'TCP_KEEPIDLE'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, idle_seconds)
    elif hasattr(socket, 'TCP_KEEPALIVE'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, idle_seconds)

    # Probe interval and count are Linux/BSD extensions; set them where present.
    if hasattr(socket, 'TCP_KEEPINTVL'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_seconds)
    if hasattr(socket, 'TCP_KEEPCNT'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)
