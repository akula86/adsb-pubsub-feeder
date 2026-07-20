# Minimum chart width in inches, and per-day horizontal growth beyond it.
MIN_CHART_WIDTH_INCHES = 6.0
WIDTH_PER_DAY_INCHES = 0.4
CHART_HEIGHT_INCHES = 4.0


def write_health_history_chart(rows: list[dict], out_path: str) -> None:
    """Write a lines-per-day bar-chart PNG to out_path.

    matplotlib is imported inside the function so the text/CSV report can run on
    a host (e.g. the Raspberry Pi) that has no plotting dependency installed.

    Args:
        rows: Per-day rollup rows from rollup_health_history.
        out_path: Destination PNG file path.
    """
    # Import here (not at module load) so only the charting path needs matplotlib.
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    # One bar per day; widen the figure as the number of days grows.
    days: list[str] = [row['day'] for row in rows]
    lines: list[int] = [row['lines'] for row in rows]
    width: float = max(MIN_CHART_WIDTH_INCHES, len(days) * WIDTH_PER_DAY_INCHES)
    figure, axis = plt.subplots(figsize=(width, CHART_HEIGHT_INCHES))
    axis.bar(days, lines)
    axis.set_title('SBS lines published per UTC day')
    axis.set_ylabel('lines')
    axis.tick_params(axis='x', rotation=90)
    figure.tight_layout()
    figure.savefig(out_path)
