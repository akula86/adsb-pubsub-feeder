import json
import logging

from ads_b.health.write_health_history_record import write_health_history_record
from ads_b.observability.throttled_logger import ThrottledLogger


class _ListHandler(logging.Handler):
    """A handler that captures emitted record messages into a list."""

    def __init__(self) -> None:
        """Initialise the captured-messages list."""
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Append the formatted message text."""
        self.messages.append(record.getMessage())


def _throttle() -> ThrottledLogger:
    """A throttle with a monotonic stub, for the failure path."""
    ticks = iter(range(1_000))
    return ThrottledLogger(logging.getLogger('t'), 5, 60.0, lambda: next(ticks))


def test_emits_json_line() -> None:
    """The record is emitted as a single json.dumps line on the given logger."""
    lg = logging.getLogger('history_probe')
    lg.handlers = []
    handler = _ListHandler()
    lg.addHandler(handler)
    lg.setLevel(logging.INFO)

    write_health_history_record({'ts': 'now', 'lines_this_interval': 9}, lg, _throttle())

    assert len(handler.messages) == 1
    assert json.loads(handler.messages[0]) == {'ts': 'now', 'lines_this_interval': 9}


def test_oserror_is_swallowed() -> None:
    """An OSError raised during emit does not propagate out of the writer."""

    class _BoomHandler(logging.Handler):
        """A handler whose emit always raises OSError."""

        def emit(self, record: logging.LogRecord) -> None:
            """Raise to simulate a disk-full rotation failure."""
            raise OSError('disk full')

    lg = logging.getLogger('history_boom')
    lg.handlers = []
    lg.addHandler(_BoomHandler())
    lg.setLevel(logging.INFO)
    lg.raiseExceptions = False

    # Must return normally despite the handler raising.
    write_health_history_record({'ts': 'now'}, lg, _throttle())
