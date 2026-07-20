from collections import defaultdict


def rollup_health_history(records: list[dict]) -> list[dict]:
    """Roll up JSONL health-history records into per-UTC-day metrics.

    Line totals sum the per-interval deltas (restart-safe). Cumulative-per-run
    metrics (uptime, disconnects, failures) are reduced per run via their max,
    then summed across the runs that occurred that day, so a mid-day restart
    neither double-counts nor drops a run.

    Args:
        records: Parsed health-history records (each a dict with ts, started_at,
            lines_this_interval, uptime_seconds, disconnects, publishes_failed).

    Returns:
        One dict per UTC day, sorted by day:
        {day, lines, uptime_seconds, disconnects, publishes_failed}.
    """
    # Per-day sum of line deltas.
    lines_by_day: dict[str, int] = defaultdict(int)
    # Per-day, per-run max of each cumulative metric.
    run_max: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {'uptime_seconds': 0, 'disconnects': 0, 'publishes_failed': 0}
    )

    # Fold each record into the day's line total and its run's running maxima.
    for record in records:
        day: str = record['ts'][:10]
        run_key: tuple[str, str] = (day, record['started_at'])
        lines_by_day[day] += record['lines_this_interval']
        maxima = run_max[run_key]
        maxima['uptime_seconds'] = max(
            maxima['uptime_seconds'], record['uptime_seconds']
        )
        maxima['disconnects'] = max(maxima['disconnects'], record['disconnects'])
        maxima['publishes_failed'] = max(
            maxima['publishes_failed'], record['publishes_failed']
        )

    # Sum each run's maxima into its day's cumulative totals.
    day_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {'uptime_seconds': 0, 'disconnects': 0, 'publishes_failed': 0}
    )
    for (day, _started_at), maxima in run_max.items():
        totals = day_totals[day]
        totals['uptime_seconds'] += maxima['uptime_seconds']
        totals['disconnects'] += maxima['disconnects']
        totals['publishes_failed'] += maxima['publishes_failed']

    # Assemble sorted per-day rows.
    rows: list[dict] = []
    for day in sorted(lines_by_day):
        totals = day_totals[day]
        rows.append(
            {
                'day': day,
                'lines': lines_by_day[day],
                'uptime_seconds': totals['uptime_seconds'],
                'disconnects': totals['disconnects'],
                'publishes_failed': totals['publishes_failed'],
            }
        )
    return rows
