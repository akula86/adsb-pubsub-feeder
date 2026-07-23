import logging

from ads_b.config.config_model import Config

logger = logging.getLogger(__name__)


def log_startup_banner(config: Config) -> None:
    """Log the operationally significant config at startup.

    Emits four INFO lines on this module's logger, which propagates to the
    root file and console handlers attached by ``configure_logging``. The
    credentials path is deliberately omitted so no secret path reaches the log.

    Args:
        config: Resolved feeder configuration to report.
    """
    # Start marker so the log shows the process launched, before any connect.
    logger.info('Feeder starting')
    # Feed target, so a wrong-host config is visible before the connect line.
    logger.info(f'Feed target: {config.feed_host}:{config.feed_port}')
    # Pub/Sub destination: the downstream target not otherwise visible in logs.
    logger.info(
        f'Pub/Sub: project={config.project_id} '
        f'topic={config.topic_id} location={config.location}'
    )
    # File paths and cadence, so an operator knows where to look.
    logger.info(
        f'Log: {config.log_file_path} '
        f'({config.log_max_megabytes}MB x{config.log_backup_count}); '
        f'Health: {config.health_file_path} '
        f'(every {config.write_interval_seconds:.0f}s)'
    )
