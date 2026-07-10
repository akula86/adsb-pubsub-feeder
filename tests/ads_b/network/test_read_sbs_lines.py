import socket

import pytest

from ads_b.network.feed_idle_error import FeedIdleError
from ads_b.network.read_sbs_lines import read_sbs_lines


class FakeSocket:
    """A fake socket yielding scripted recv() results for tests.

    Each script entry is either bytes to return, the string 'timeout' to raise
    socket.timeout, or b'' to signal peer close.
    """

    def __init__(self, script: list[object]) -> None:
        """Store the scripted recv() results."""
        self._script = list(script)

    def recv(self, _bufsize: int) -> bytes:
        """Return the next scripted result, raising socket.timeout when scripted."""
        if not self._script:
            raise AssertionError('recv called more times than scripted')
        item = self._script.pop(0)
        if item == 'timeout':
            raise socket.timeout()
        assert isinstance(item, bytes)
        return item


def test_splits_lines_across_partial_reads() -> None:
    """Lines spanning multiple recv() calls are reassembled and split on newline.

    The first fragment (before the first newline) is a partial line left over
    from before we connected, so it is discarded; the first line yielded is the
    first one that began after connect.
    """
    sock = FakeSocket([b'PARTIAL,1,1,ABC', b'123,1\nMSG,4,1', b',1,DEF456\n'])

    gen = read_sbs_lines(sock, idle_timeout_seconds=60.0)
    line1 = next(gen)

    # 'PARTIAL,1,1,ABC123,1' is dropped as the pre-connect fragment; the first
    # complete post-connect line is the one that follows the first newline.
    assert line1 == 'MSG,4,1,1,DEF456'


def test_discards_leading_fragment_on_first_connect() -> None:
    """The bytes before the first newline are discarded as a torn pre-connect line."""
    # We connect mid-stream: 'GED,1,1,TAIL' is the tail of a line we never saw
    # the start of. It must not be yielded.
    sock = FakeSocket([b'GED,1,1,TAIL\nMSG,3,1,1,FULL\n'])

    gen = read_sbs_lines(sock, idle_timeout_seconds=60.0)

    # The first yielded line is the first complete one after the first newline.
    assert next(gen) == 'MSG,3,1,1,FULL'


def test_empty_recv_raises_connection_error() -> None:
    """An empty recv (peer closed) raises ConnectionError."""
    # The first fragment 'JUNK' is discarded; 'MSG,1,1,1,AAA' is the first
    # complete post-connect line.
    sock = FakeSocket([b'JUNK\nMSG,1,1,1,AAA\n', b''])

    gen = read_sbs_lines(sock, idle_timeout_seconds=60.0)
    assert next(gen) == 'MSG,1,1,1,AAA'
    with pytest.raises(ConnectionError):
        next(gen)


def test_idle_timeout_raises_feed_idle_error() -> None:
    """No bytes past the idle timeout raises FeedIdleError after an idle tick."""
    # Clock: startup=0, first timeout still in budget (10 < 60 → tick),
    # second timeout past budget (100 >= 60 → raise).
    times = iter([0.0, 10.0, 100.0])
    sock = FakeSocket(['timeout', 'timeout'])

    gen = read_sbs_lines(sock, idle_timeout_seconds=60.0, monotonic=lambda: next(times))
    # First timeout is within budget: an idle tick, not an error.
    assert next(gen) is None
    # Second timeout is past the budget: the watchdog fires.
    with pytest.raises(FeedIdleError):
        next(gen)


def test_socket_timeout_within_idle_budget_yields_tick_then_line() -> None:
    """A socket timeout inside the idle budget yields a None tick, then the line."""
    # Clock stays within the idle budget across the timeout, then data arrives.
    times = iter([0.0, 0.0, 1.0, 1.0])
    # 'FRAG' is the discarded pre-connect fragment; the first full line follows.
    sock = FakeSocket(['timeout', b'FRAG\nMSG,8,1,1,BBB\n'])

    gen = read_sbs_lines(sock, idle_timeout_seconds=60.0, monotonic=lambda: next(times))
    # The idle tick lets the caller run its flush timer during a lull.
    assert next(gen) is None
    # The first complete post-connect line follows once bytes arrive.
    assert next(gen) == 'MSG,8,1,1,BBB'
