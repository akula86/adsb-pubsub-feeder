import argparse
import logging
import os
import sys
from pathlib import Path

from google.cloud import pubsub_v1

from ads_b.config.load_config import load_config
from ads_b.config.config_model import Config
from ads_b.lifecycle.configure_health_history_logging import (
    configure_health_history_logging,
)
from ads_b.lifecycle.configure_logging import configure_logging
from ads_b.lifecycle.install_shutdown_handlers import install_shutdown_handlers
from ads_b.lifecycle.log_startup_banner import log_startup_banner
from ads_b.lifecycle.run_feeder import run_feeder
from ads_b.lifecycle.shutdown_flag import ShutdownFlag

logger = logging.getLogger(__name__)

# Exit code for a clean SIGINT/SIGTERM-triggered shutdown.
EXIT_SIGINT = 130
# Default config and env file locations.
DEFAULT_APP_TOML = 'app.toml'
DEFAULT_ENV = '~/.env'


def main() -> None:
    """Parse arguments, wire dependencies, and run the feeder until signalled."""
    # Parse CLI arguments for the config and env file paths.
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description='Forward SBS feed to Google Pub/Sub.'
    )
    parser.add_argument('--app-toml', default=DEFAULT_APP_TOML, help='Path to app.toml')
    parser.add_argument('--env', default=DEFAULT_ENV, help='Path to the .env file')
    args: argparse.Namespace = parser.parse_args()

    # Load non-secret config and the credential path first, so the log file
    # path is known before logging is configured.
    config: Config = load_config(Path(args.app_toml), Path(args.env).expanduser())

    # Configure a rotating log file plus console output from the loaded config.
    configure_logging(
        config.log_file_path,
        config.log_max_megabytes,
        config.log_backup_count,
    )

    # Log the operationally significant config now that handlers are attached.
    log_startup_banner(config)

    # Configure the separate rotating JSONL health-history log.
    configure_health_history_logging(
        config.health_log_file_path,
        config.health_log_max_megabytes,
        config.health_log_backup_count,
    )

    # Quiet gRPC's native (C-core) stderr, which floods on FD exhaustion. The
    # bounded backlog should prevent that, but this bounds the blast radius.
    os.environ.setdefault('GRPC_VERBOSITY', 'ERROR')

    # Build the Pub/Sub publisher from the service-account key named in ~/.env,
    # so authentication never depends on an ambient GOOGLE_APPLICATION_CREDENTIALS.
    publisher: pubsub_v1.PublisherClient = (
        pubsub_v1.PublisherClient.from_service_account_file(config.credentials_path)
    )
    topic_path: str = publisher.topic_path(config.project_id, config.topic_id)

    # Install signal handlers that flip a shutdown flag the feeder loop reads.
    flag: ShutdownFlag = ShutdownFlag()
    install_shutdown_handlers(flag)

    # Run until a signal requests shutdown; run_feeder writes the final health
    # file and drains on exit.
    run_feeder(
        config,
        publisher,
        topic_path,
        should_continue=lambda: not flag.is_requested(),
    )

    # Exit with the conventional SIGINT code after a signal-triggered shutdown.
    if flag.is_requested():
        sys.exit(EXIT_SIGINT)


if __name__ == '__main__':
    main()
