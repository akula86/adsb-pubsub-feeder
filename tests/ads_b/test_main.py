from unittest import mock

from ads_b.config.config_model import Config
from ads_b.main import main


def _config(credentials_path: str) -> Config:
    """Build a Config with a given credential path and inert other fields."""
    return Config(
        feed_host='host',
        feed_port=30003,
        project_id='proj',
        topic_id='topic',
        location='SJC',
        initial_backoff_seconds=1.0,
        max_backoff_seconds=30.0,
        feed_idle_timeout_seconds=60.0,
        keepalive_idle_seconds=1,
        keepalive_interval_seconds=3,
        keepalive_max_fails=5,
        health_file_path='/tmp/h.json',
        write_interval_seconds=10.0,
        health_tick_seconds=1.0,
        health_log_file_path='/tmp/h-history.log',
        health_log_max_megabytes=5,
        health_log_backup_count=3,
        log_file_path='/tmp/a.log',
        log_max_megabytes=5,
        log_backup_count=3,
        max_pending=1_000,
        error_sample_count=5,
        error_summary_interval_seconds=60.0,
        credentials_path=credentials_path,
    )


def test_publisher_built_from_config_credentials_path(monkeypatch) -> None:
    """main builds the publisher from the config's credential path, not the env var."""
    # Drive main with no CLI args and a controlled config.
    monkeypatch.setattr('sys.argv', ['ads-b'])
    monkeypatch.setattr('ads_b.main.load_config', lambda _toml, _env: _config('/keys/sa.json'))
    monkeypatch.setattr('ads_b.main.configure_logging', lambda *a, **k: None)
    monkeypatch.setattr('ads_b.main.install_shutdown_handlers', lambda _flag: None)
    monkeypatch.setattr('ads_b.main.run_feeder', lambda *a, **k: None)

    # Capture the PublisherClient construction path.
    fake_client = mock.MagicMock()
    fake_client.topic_path.return_value = 'projects/proj/topics/topic'
    from_file = mock.MagicMock(return_value=fake_client)
    monkeypatch.setattr(
        'ads_b.main.pubsub_v1.PublisherClient.from_service_account_file', from_file
    )

    main()

    # The publisher was built from the config's credential path.
    from_file.assert_called_once_with('/keys/sa.json')
