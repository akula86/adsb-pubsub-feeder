import logging
import tomllib
from pathlib import Path

from ads_b.config.config_model import Config
from ads_b.config.read_credentials_path import read_credentials_path
from ads_b.config.require_pubsub_location import require_pubsub_location

logger = logging.getLogger(__name__)


def load_config(app_toml_path: Path, env_path: Path) -> Config:
    """Load non-secret config from app.toml and the credential path from .env.

    Args:
        app_toml_path: Path to the non-secret TOML config file.
        env_path: Path to the .env file holding the credential path.

    Returns:
        A populated Config instance.

    Raises:
        KeyError: If the credential key is missing from the .env file.
        ValueError: If the [pubsub] location is missing, blank, or still the
            template placeholder in the app.toml file.
    """
    # Read and parse the non-secret TOML config into nested dicts.
    with app_toml_path.open('rb') as handle:
        raw: dict = tomllib.load(handle)

    # Validate and normalise the location up front so a missing or placeholder
    # value fails with a clear, file-naming message instead of a bare KeyError.
    location: str = require_pubsub_location(raw, app_toml_path)

    # Read the secret credential path from the separate .env file.
    credentials_path: str = read_credentials_path(env_path)

    # Assemble the frozen Config from the parsed sections and the credential path.
    return Config(
        feed_host=raw['feed']['host'],
        feed_port=raw['feed']['port'],
        project_id=raw['pubsub']['project_id'],
        topic_id=raw['pubsub']['topic_id'],
        location=location,
        initial_backoff_seconds=raw['reconnect']['initial_backoff_seconds'],
        max_backoff_seconds=raw['reconnect']['max_backoff_seconds'],
        feed_idle_timeout_seconds=raw['watchdog']['feed_idle_timeout_seconds'],
        keepalive_idle_seconds=raw['keepalive']['idle_seconds'],
        keepalive_interval_seconds=raw['keepalive']['interval_seconds'],
        keepalive_max_fails=raw['keepalive']['max_fails'],
        health_file_path=raw['health']['health_file_path'],
        write_interval_seconds=raw['health']['write_interval_seconds'],
        health_tick_seconds=raw['health']['health_tick_seconds'],
        health_log_file_path=raw['health']['health_log_file_path'],
        health_log_max_megabytes=raw['health']['health_log_max_megabytes'],
        health_log_backup_count=raw['health']['health_log_backup_count'],
        log_file_path=raw['logging']['log_file_path'],
        log_max_megabytes=raw['logging']['max_megabytes'],
        log_backup_count=raw['logging']['backup_count'],
        max_pending=raw['publish']['max_pending'],
        error_sample_count=raw['logging']['error_sample_count'],
        error_summary_interval_seconds=raw['logging']['error_summary_interval_seconds'],
        credentials_path=credentials_path,
    )
