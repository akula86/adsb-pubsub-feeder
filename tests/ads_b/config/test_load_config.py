from pathlib import Path

from ads_b.config.load_config import load_config
from ads_b.config.config_model import Config

APP_TOML = """\
[feed]
host = "10.0.0.5"
port = 30003

[pubsub]
project_id = "test-project"
topic_id = "test-topic"

[reconnect]
initial_backoff_seconds = 1.0
max_backoff_seconds = 30.0

[watchdog]
feed_idle_timeout_seconds = 60.0

[keepalive]
idle_seconds = 1
interval_seconds = 3
max_fails = 5

[health]
health_file_path = "/tmp/health.json"
write_interval_seconds = 300.0
health_tick_seconds = 1.0

[logging]
log_file_path = "/tmp/adsb.log"
max_megabytes = 5
backup_count = 3
error_sample_count = 5
error_summary_interval_seconds = 60.0

[publish]
max_pending = 1000
"""


def _write(tmp_path: Path, app_toml: str, env: str) -> tuple[Path, Path]:
    """Write app.toml and .env fixtures, return their paths."""
    app_path = tmp_path / 'app.toml'
    env_path = tmp_path / '.env'
    app_path.write_text(app_toml)
    env_path.write_text(env)
    return app_path, env_path


def test_load_config_reads_all_fields(tmp_path: Path) -> None:
    """load_config parses every field from app.toml and the credential path from .env."""
    app_path, env_path = _write(
        tmp_path, APP_TOML, 'GOOGLE_APPLICATION_CREDENTIALS=/opt/adsb/service-account.json\n'
    )

    config = load_config(app_path, env_path)

    assert isinstance(config, Config)
    assert config.feed_host == '10.0.0.5'
    assert config.feed_port == 30003
    assert config.project_id == 'test-project'
    assert config.topic_id == 'test-topic'
    assert config.initial_backoff_seconds == 1.0
    assert config.max_backoff_seconds == 30.0
    assert config.feed_idle_timeout_seconds == 60.0
    assert config.keepalive_idle_seconds == 1
    assert config.keepalive_interval_seconds == 3
    assert config.keepalive_max_fails == 5
    assert config.health_file_path == '/tmp/health.json'
    assert config.write_interval_seconds == 300.0
    assert config.health_tick_seconds == 1.0
    assert config.log_file_path == '/tmp/adsb.log'
    assert config.log_max_megabytes == 5
    assert config.log_backup_count == 3
    assert config.max_pending == 1_000
    assert config.error_sample_count == 5
    assert config.error_summary_interval_seconds == 60.0
    assert config.credentials_path == '/opt/adsb/service-account.json'
