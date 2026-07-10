import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ads_b.lifecycle.configure_logging import configure_logging


def _teardown_root() -> None:
    """Remove and close handlers added to the root logger during a test."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


def test_installs_rotating_file_handler(tmp_path: Path) -> None:
    """A RotatingFileHandler is attached with the configured size and backups."""
    log_path = tmp_path / 'adsb.log'
    try:
        configure_logging(str(log_path), max_megabytes=5, backup_count=3)

        root = logging.getLogger()
        rotating = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(rotating) == 1
        handler = rotating[0]
        # 5 MB expressed in bytes, and three retained backups.
        assert handler.maxBytes == 5 * 1_024 * 1_024
        assert handler.backupCount == 3
    finally:
        _teardown_root()


def test_log_filename_is_the_configured_path(tmp_path: Path) -> None:
    """The active log file is always the configured path (stable name)."""
    log_path = tmp_path / 'adsb.log'
    try:
        configure_logging(str(log_path), max_megabytes=5, backup_count=3)

        logging.getLogger('probe').warning('hello')

        # The live log file has the exact configured name; rollovers only ever
        # add .1/.2/.3 siblings, never rename the active file.
        assert log_path.exists()
        assert 'hello' in log_path.read_text()
    finally:
        _teardown_root()


def test_also_logs_to_console(tmp_path: Path) -> None:
    """A console stream handler is added alongside the rotating file handler.

    The root logger may already carry pytest's own capture handlers, so this
    asserts on the handlers configure_logging itself adds by capturing the
    root's handler set before and after the call.
    """
    log_path = tmp_path / 'adsb.log'
    root = logging.getLogger()
    before: set[int] = {id(h) for h in root.handlers}
    try:
        configure_logging(str(log_path), max_megabytes=5, backup_count=3)

        # The handlers this call added, isolated from any pre-existing ones.
        added: list[logging.Handler] = [h for h in root.handlers if id(h) not in before]
        console_handlers: list[logging.Handler] = [
            h
            for h in added
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, RotatingFileHandler)
        ]
        # One rotating file handler and one plain console handler were added.
        assert len(added) == 2
        assert len(console_handlers) == 1
    finally:
        _teardown_root()
