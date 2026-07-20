from ads_b.reporting.rollup_health_history import rollup_health_history


def _rec(ts: str, started_at: str, delta: int, uptime: int,
         disconnects: int = 0, failed: int = 0) -> dict:
    """Build a minimal history record for rollup tests."""
    return {
        'ts': ts,
        'started_at': started_at,
        'lines_this_interval': delta,
        'uptime_seconds': uptime,
        'disconnects': disconnects,
        'publishes_failed': failed,
    }


def test_single_run_day_sums_delta_and_takes_max_uptime() -> None:
    """One run: lines sum, uptime is the run's max."""
    run = '2026-07-13T00:00:00+00:00'
    records = [
        _rec('2026-07-13T00:05:00+00:00', run, 100, 300),
        _rec('2026-07-13T00:10:00+00:00', run, 150, 600),
    ]

    rows = rollup_health_history(records)

    assert len(rows) == 1
    assert rows[0]['day'] == '2026-07-13'
    assert rows[0]['lines'] == 250
    assert rows[0]['uptime_seconds'] == 600


def test_restart_within_day_sums_lines_and_uptime_across_runs() -> None:
    """A restart splits the day into two runs; lines and uptime add up."""
    run_a = '2026-07-14T00:00:00+00:00'
    run_b = '2026-07-14T05:00:00+00:00'
    records = [
        _rec('2026-07-14T04:55:00+00:00', run_a, 800, 17700, disconnects=1),
        _rec('2026-07-14T05:05:00+00:00', run_b, 400, 300, disconnects=0),
        _rec('2026-07-14T05:10:00+00:00', run_b, 350, 600, disconnects=2),
    ]

    rows = rollup_health_history(records)

    assert len(rows) == 1
    # Lines: 800 + 400 + 350 = 1550 (max would wrongly give 800).
    assert rows[0]['lines'] == 1550
    # Uptime: run A max 17700 + run B max 600 = 18300.
    assert rows[0]['uptime_seconds'] == 18300
    # Disconnects: run A max 1 + run B max 2 = 3.
    assert rows[0]['disconnects'] == 3


def test_multiple_days_sorted() -> None:
    """Rows span multiple UTC days and come back sorted by day."""
    run = '2026-07-13T00:00:00+00:00'
    records = [
        _rec('2026-07-14T00:05:00+00:00', run, 10, 100),
        _rec('2026-07-13T00:05:00+00:00', run, 20, 100),
    ]

    rows = rollup_health_history(records)

    assert [r['day'] for r in rows] == ['2026-07-13', '2026-07-14']
