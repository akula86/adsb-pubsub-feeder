import logging
from logging.handlers import RotatingFileHandler

from ads_b.lifecycle.bytes_per_megabyte import BYTES_PER_MEGABYTE

logger = logging.getLogger(__name__)

# The dedicated logger name for JSONL health-history records.
HEALTH_HISTORY_LOGGER = 'health_history'
# Bare format: the record's own JSON is the entire line, no prefix.
HISTORY_FORMAT = '%(message)s'


def configure_health_history_logging(
    health_log_file_path: str,
    max_megabytes: int,
    backup_count: int,
) -> None:
    """Attach a rotating JSONL file handler to the health-history logger.

    The handler writes each record as a bare line (no timestamp or level
    prefix) so the file is pure JSONL. The logger does not propagate, so health
    records never leak into the main log or the console.

    Args:
        health_log_file_path: Fixed path of the active history file (never renamed).
        max_megabytes: Maximum size of a single history file before it rolls over.
        backup_count: Number of rolled-over history files to retain.
    """
    # A formatter that emits only the message, so lines are valid JSON.
    formatter: logging.Formatter = logging.Formatter(HISTORY_FORMAT)

    # Size-rotating handler: bounded on-disk footprint, stable active name.
    file_handler: RotatingFileHandler = RotatingFileHandler(
        health_log_file_path,
        maxBytes=max_megabytes * BYTES_PER_MEGABYTE,
        backupCount=backup_count,
    )
    file_handler.setFormatter(formatter)

    # Configure the dedicated logger: INFO level, no propagation to the root.
    history_logger: logging.Logger = logging.getLogger(HEALTH_HISTORY_LOGGER)
    history_logger.setLevel(logging.INFO)
    history_logger.propagate = False
    history_logger.addHandler(file_handler)
