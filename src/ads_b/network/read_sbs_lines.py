import logging
import socket
import time
from collections.abc import Callable, Iterator

from ads_b.network.feed_idle_error import FeedIdleError

logger = logging.getLogger(__name__)

# Bytes to request per recv() call.
RECV_BUFFER_BYTES = 4_096


def read_sbs_lines(
    sock: socket.socket,
    idle_timeout_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
) -> Iterator[str | None]:
    """Yield decoded, newline-stripped SBS lines from a socket.

    The socket must already have a read timeout set (via settimeout) so recv()
    returns control periodically even on a quiet feed. On each recv() that times
    out with no bytes, this yields None as a tick so the caller can run its own
    time-based work (e.g. a flush timer) during a lull. Partial lines spanning
    recv() boundaries are retained and only yielded once terminated by a newline.

    Args:
        sock: A connected socket with a read timeout applied.
        idle_timeout_seconds: Raise FeedIdleError if no bytes arrive in this window.
        monotonic: Injectable monotonic clock (defaults to time.monotonic).

    Yields:
        Each decoded, stripped, non-empty SBS line, and None on each idle tick.

    Raises:
        FeedIdleError: If no bytes arrive within idle_timeout_seconds.
        ConnectionError: If the peer closes the connection (empty recv).
    """
    # Buffer for the trailing partial line that has no newline yet.
    buffer: str = ''
    # Timestamp of the last time any bytes were received.
    last_data_at: float = monotonic()
    # We connect mid-stream, so the bytes before the first newline are the tail
    # of a line whose start we never saw. Discard that fragment until the first
    # newline has been seen, so the first yielded line is complete.
    first_line_seen: bool = False

    while True:
        try:
            # Attempt to read a chunk; the socket timeout bounds this call.
            chunk: bytes = sock.recv(RECV_BUFFER_BYTES)
        except socket.timeout:
            # No data this cycle; fail only if the whole idle budget has elapsed.
            if monotonic() - last_data_at >= idle_timeout_seconds:
                raise FeedIdleError(
                    f'No feed data for {idle_timeout_seconds:.0f}s; forcing reconnect'
                )
            # Still within budget: emit an idle tick so the caller can flush.
            yield None
            continue

        # An empty recv means the peer closed the connection.
        if not chunk:
            raise ConnectionError('Feed closed the connection')

        # Bytes arrived; reset the idle timer and decode into the line buffer.
        last_data_at = monotonic()
        buffer += chunk.decode('utf-8', errors='replace')

        # Split off every complete line, keeping the trailing fragment buffered.
        *complete_lines, buffer = buffer.split('\n')

        # On this connection's first newline, drop the leading fragment: it is a
        # partial line from before we connected, not a complete SBS record.
        if not first_line_seen and complete_lines:
            complete_lines = complete_lines[1:]
            first_line_seen = True

        for line in complete_lines:
            # Drop surrounding whitespace (e.g. a trailing \r) before yielding.
            stripped: str = line.strip()
            # Skip blank lines (e.g. an empty keepalive or bare \r).
            if stripped:
                yield stripped
