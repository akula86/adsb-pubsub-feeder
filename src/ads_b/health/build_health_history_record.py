from datetime import datetime

from ads_b.health.feeder_stats import FeederStats


def build_health_history_record(
    stats: FeederStats,
    now: datetime,
    in_flight: int,
    lines_this_interval: int,
) -> dict:
    """Build one JSONL-ready health-history record for the current interval.

    The record is the full stats snapshot plus a top-level write timestamp and
    the per-interval line delta. The delta (rather than a cumulative total) is
    what makes per-day line totals restart-safe: they are summed, not maxed.

    Args:
        stats: The feeder stats to snapshot.
        now: The write time, used for uptime and as the record timestamp.
        in_flight: Publish futures submitted but not yet reconciled.
        lines_this_interval: Lines published since the previous record.

    Returns:
        A JSON-serialisable dict: {ts, lines_this_interval, ...snapshot fields}.
    """
    # ts and the delta lead; the snapshot (which includes started_at, the run
    # identifier) is merged in after them.
    return {
        'ts': now.isoformat(),
        'lines_this_interval': lines_this_interval,
        **stats.snapshot(now, in_flight),
    }
