import socket

from ads_b.network.apply_keepalive import apply_keepalive


class RecordingSocket:
    """A fake socket recording setsockopt calls."""

    def __init__(self) -> None:
        """Initialise the recorded-options list."""
        self.opts: list[tuple[int, int, int]] = []

    def setsockopt(self, level: int, optname: int, value: int) -> None:
        """Record a setsockopt call."""
        self.opts.append((level, optname, value))


def test_always_enables_keepalive() -> None:
    """SO_KEEPALIVE is enabled on every platform."""
    sock = RecordingSocket()

    apply_keepalive(sock, idle_seconds=1, interval_seconds=3, max_fails=5)

    # SO_KEEPALIVE exists everywhere and must always be turned on.
    assert (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) in sock.opts


def test_sets_idle_time_via_available_constant() -> None:
    """The idle time is set through whichever idle constant this platform has.

    Linux exposes TCP_KEEPIDLE; macOS/BSD exposes TCP_KEEPALIVE for the same
    idle-before-first-probe setting. At least one is present on supported
    platforms, and the idle value must be routed to it.
    """
    sock = RecordingSocket()

    apply_keepalive(sock, idle_seconds=7, interval_seconds=3, max_fails=5)

    # Collect the (optname, value) pairs set at the TCP level.
    tcp_opts = [(name, val) for level, name, val in sock.opts if level == socket.IPPROTO_TCP]
    idle_names = {
        getattr(socket, attr)
        for attr in ('TCP_KEEPIDLE', 'TCP_KEEPALIVE')
        if hasattr(socket, attr)
    }
    # The idle value (7) was set through one of the platform's idle constants.
    assert any(name in idle_names and val == 7 for name, val in tcp_opts)


def test_sets_interval_and_count_when_supported() -> None:
    """Probe interval and count are set when the platform provides those options."""
    sock = RecordingSocket()

    apply_keepalive(sock, idle_seconds=1, interval_seconds=3, max_fails=5)

    # Guard each on hasattr so the assertion holds on platforms lacking them.
    if hasattr(socket, 'TCP_KEEPINTVL'):
        assert (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3) in sock.opts
    if hasattr(socket, 'TCP_KEEPCNT'):
        assert (socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5) in sock.opts
