import logging
import socket

logger = logging.getLogger(__name__)


def close_socket(sock: socket.socket) -> None:
    """Close a socket, suppressing errors from an already-broken connection.

    Args:
        sock: The socket to close.
    """
    # A dropped feed may already have broken the socket; ignore close errors.
    try:
        sock.close()
    except OSError:
        pass
