import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ads_b.lifecycle.configure_health_history_logging import (
    configure_health_history_logging,
)


def _teardown() -> None:
    """Remove and close handlers on the health_history logger after a test."""
    lg = logging.getLogger('health_history')
    for handler in list(lg.handlers):
        lg.removeHandler(handler)
        handler.close()


def test_installs_rotating_handler_with_bounds(tmp_path: Path) -> None:
    """A single RotatingFileHandler is attached with the configured bounds."""
    log_path = tmp_path / 'history.log'
    try:
        configure_health_history_logging(str(log_path), max_megabytes=5, backup_count=3)

        lg = logging.getLogger('health_history')
        rotating = [h for h in lg.handlers if isinstance(h, RotatingFileHandler)]
        assert len(rotating) == 1
        assert rotating[0].maxBytes == 5 * 1_024 * 1_024
        assert rotating[0].backupCount == 3
    finally:
        _teardown()


def test_writes_pure_json_lines_and_does_not_propagate(tmp_path: Path) -> None:
    """Records are written with no log prefix and do not reach the root logger."""
    log_path = tmp_path / 'history.log'
    try:
        configure_health_history_logging(str(log_path), max_megabytes=5, backup_count=3)

        lg = logging.getLogger('health_history')
        assert lg.propagate is False
        lg.info(json.dumps({'ts': 'now', 'lines_this_interval': 42}))

        # The line is bare JSON: no timestamp/level prefix, parses directly.
        line = log_path.read_text().strip()
        parsed = json.loads(line)
        assert parsed == {'ts': 'now', 'lines_this_interval': 42}
    finally:
        _teardown()
