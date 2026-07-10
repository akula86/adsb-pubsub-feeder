import logging
import signal
from types import FrameType

from ads_b.lifecycle.shutdown_flag import ShutdownFlag

logger = logging.getLogger(__name__)


def install_shutdown_handlers(flag: ShutdownFlag) -> None:
    """Register SIGINT and SIGTERM handlers that set the shutdown flag.

    Args:
        flag: The ShutdownFlag to set when a shutdown signal arrives.
    """

    def handle_signal(signum: int, _frame: FrameType | None) -> None:
        """Flag a graceful shutdown on SIGINT/SIGTERM."""
        # Log which signal arrived, then flip the flag the feeder loop reads.
        logger.info(f'Received signal {signum}; shutting down after final health write')
        flag.request()

    # Handle Ctrl-C (SIGINT) and service-manager stop (SIGTERM) the same way.
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
