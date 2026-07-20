import csv

# Fixed CSV column order, matching the text-table columns.
CSV_FIELDS = ['day', 'lines', 'uptime_seconds', 'disconnects', 'publishes_failed']


def write_health_history_csv(rows: list[dict], csv_path: str) -> None:
    """Write per-day rollup rows as CSV to csv_path.

    Args:
        rows: Per-day rollup rows from rollup_health_history.
        csv_path: Destination CSV file path (overwritten).
    """
    # Write a header row followed by one row per day, in the fixed column order.
    with open(csv_path, 'w', encoding='utf-8', newline='') as handle:
        writer: csv.DictWriter = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
