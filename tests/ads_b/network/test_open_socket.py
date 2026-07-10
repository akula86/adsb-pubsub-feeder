import socket
import threading

from ads_b.network.open_socket import open_socket


def test_connects_sets_timeout_and_keepalive() -> None:
    """open_socket connects, applies the read timeout, and enables keepalive."""
    # Bind an ephemeral loopback listener to accept one connection.
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 0))
    server.listen(1)
    host, port = server.getsockname()

    # Accept the incoming connection on a background thread.
    accepted: list[socket.socket] = []

    def accept_one() -> None:
        conn, _addr = server.accept()
        accepted.append(conn)

    thread = threading.Thread(target=accept_one)
    thread.start()

    # Open the client socket under test with keepalive params.
    client = open_socket(host, port, 3.5, 1, 3, 5)
    thread.join()

    # Read timeout applied.
    assert client.gettimeout() == 3.5
    # Keepalive enabled at the socket level.
    # getsockopt reports keepalive as normalized 1 on Linux but as the raw
    # non-zero option value on macOS/BSD; assert enabled (truthy) for both.
    assert client.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) != 0

    # Clean up all sockets.
    client.close()
    if accepted:
        accepted[0].close()
    server.close()
