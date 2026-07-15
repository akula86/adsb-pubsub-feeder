from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Resolved, non-secret feeder configuration plus the credential file path."""

    # Feed source: the fr24feed BaseStation TCP endpoint.
    feed_host: str
    feed_port: int
    # Pub/Sub destination identifiers.
    project_id: str
    topic_id: str
    # Feeder location: IATA code of the nearest airport (e.g. SJC), published
    # as a message attribute on every message.
    location: str
    # Reconnect backoff bounds for a dropped feed.
    initial_backoff_seconds: float
    max_backoff_seconds: float
    # Read-idle watchdog: force reconnect after this long with no bytes.
    feed_idle_timeout_seconds: float
    # TCP keepalive: OS-level dead-peer detection.
    keepalive_idle_seconds: int
    keepalive_interval_seconds: int
    keepalive_max_fails: int
    # Health file: where to write, how often, and the loop tick cadence.
    health_file_path: str
    write_interval_seconds: float
    health_tick_seconds: float
    # Rotating log file: fixed path, per-file size cap, and retained backups.
    log_file_path: str
    log_max_megabytes: int
    log_backup_count: int
    # Backlog cap: drop the oldest tracked publish when pending reaches this.
    max_pending: int
    # Log-flood control: full-detail samples per error key, then periodic summary.
    error_sample_count: int
    error_summary_interval_seconds: float
    # Path to the Google service-account key file (from ~/.env, never inlined).
    credentials_path: str
