from ads_b.network.close_socket import close_socket


class ClosingSocket:
    """A fake socket that records whether close() was called."""

    def __init__(self) -> None:
        """Start in the not-yet-closed state."""
        self.closed = False

    def close(self) -> None:
        """Record that close was invoked."""
        self.closed = True


class BrokenSocket:
    """A fake socket whose close() raises OSError."""

    def close(self) -> None:
        """Raise as an already-broken connection would."""
        raise OSError('already closed')


def test_closes_normal_socket() -> None:
    """A healthy socket is closed."""
    sock = ClosingSocket()

    close_socket(sock)  # type: ignore[arg-type]

    assert sock.closed is True


def test_suppresses_oserror() -> None:
    """An OSError from close() is swallowed, not propagated."""
    # Should not raise despite the socket's broken close().
    close_socket(BrokenSocket())  # type: ignore[arg-type]
