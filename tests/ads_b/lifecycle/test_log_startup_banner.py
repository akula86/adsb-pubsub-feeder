import logging

from ads_b.config.config_model import Config
from ads_b.lifecycle.log_startup_banner import log_startup_banner


def _config() -> Config:
    """Build a Config with representative, inert field values."""
    return Config(
        feed_host='192.168.68.84',
        feed_port=30003,
        project_id='paulleroy',
        topic_id='flight-transponder',
        location='KSJC',
        initial_backoff_seconds=1.0,
        max_backoff_seconds=30.0,
        feed_idle_timeout_seconds=60.0,
        keepalive_idle_seconds=1,
        keepalive_interval_seconds=3,
        keepalive_max_fails=5,
        health_file_path='/opt/adsb/health.json',
        write_interval_seconds=300.0,
        health_tick_seconds=1.0,
        health_log_file_path='/opt/adsb/health-history.log',
        health_log_max_megabytes=5,
        health_log_backup_count=3,
        log_file_path='/opt/adsb/adsb.log',
        log_max_megabytes=5,
        log_backup_count=3,
        max_pending=1_000,
        error_sample_count=5,
        error_summary_interval_seconds=60.0,
        credentials_path='/keys/should-not-appear.json',
    )


def test_banner_logs_expected_lines(caplog) -> None:
    """The banner emits the start marker, feed target, Pub/Sub, and file lines."""
    with caplog.at_level(logging.INFO):
        log_startup_banner(_config())

    messages = [record.getMessage() for record in caplog.records]
    assert 'Feeder starting' in messages
    assert 'Feed target: 192.168.68.84:30003' in messages
    assert (
        'Pub/Sub: project=paulleroy topic=flight-transponder location=KSJC'
        in messages
    )
    assert (
        'Log: /opt/adsb/adsb.log (5MB x3); '
        'Health: /opt/adsb/health.json (every 300s)'
        in messages
    )


def test_banner_never_logs_credentials_path(caplog) -> None:
    """The credentials path must never be emitted in the banner."""
    with caplog.at_level(logging.INFO):
        log_startup_banner(_config())

    joined = '\n'.join(record.getMessage() for record in caplog.records)
    assert 'should-not-appear' not in joined
