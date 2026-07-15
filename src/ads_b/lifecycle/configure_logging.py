import logging
from logging.handlers import RotatingFileHandler

from ads_b.lifecycle.bytes_per_megabyte import BYTES_PER_MEGABYTE

logger = logging.getLogger(__name__)

# Shared log line format for both the file and the console.
LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'


def configure_logging(
    log_file_path: str,
    max_megabytes: int,
    backup_count: int,
) -> None:
    """Attach a rotating file handler and a console handler to the root logger.

    The active log file always keeps ``log_file_path`` as its name; on reaching
    the size cap it rolls over to numbered siblings (``.1`` .. ``.N``) and the
    oldest beyond ``backup_count`` is discarded, so disk use is bounded. Logs
    also continue to the console (stderr) so an operator watching the terminal
    sees the same lines.

    Args:
        log_file_path: Fixed path of the active log file (never renamed).
        max_megabytes: Maximum size of a single log file before it rolls over.
        backup_count: Number of rolled-over files to retain.
    """
    # A single formatter shared by both destinations for consistent output.
    formatter: logging.Formatter = logging.Formatter(LOG_FORMAT)

    # Size-rotating file handler: bounded on-disk footprint, stable active name.
    file_handler: RotatingFileHandler = RotatingFileHandler(
        log_file_path,
        maxBytes=max_megabytes * BYTES_PER_MEGABYTE,
        backupCount=backup_count,
    )
    file_handler.setFormatter(formatter)

    # Console handler so the same lines still reach stderr for live viewing.
    console_handler: logging.StreamHandler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configure the root logger so every module's logger propagates to both.
    root: logging.Logger = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
