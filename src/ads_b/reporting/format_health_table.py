# Seconds in a full UTC day, for the uptime-percentage column.
SECONDS_PER_DAY = 86_400


def format_health_table(rows: list[dict]) -> str:
    """Format per-day rollup rows as an aligned, human-readable text table.

    Numbers >= 1000 use comma grouping for readability, per project output
    conventions. Uptime is shown as a percentage of a full UTC day, capped at
    100%.

    Args:
        rows: Per-day rollup rows from rollup_health_history.

    Returns:
        The full table as a single string (header plus one line per day),
        newline-terminated.
    """
    # Header line, then one formatted line per day.
    lines: list[str] = [
        f'{"Day":<12}{"Lines":>14}{"Uptime%":>9}{"Disc":>6}{"Fail":>6}'
    ]
    for row in rows:
        # Cap uptime at 100% (a full day is SECONDS_PER_DAY of uptime).
        uptime_pct: float = min(100.0, row['uptime_seconds'] / SECONDS_PER_DAY * 100)
        # Comma-group the line count for user-facing output.
        lines.append(
            f'{row["day"]:<12}{row["lines"]:>14,}{uptime_pct:>8.1f}%'
            f'{row["disconnects"]:>6}{row["publishes_failed"]:>6}'
        )
    return '\n'.join(lines) + '\n'
