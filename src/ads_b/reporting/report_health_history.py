import logging
import sys
from typing import TextIO

from ads_b.reporting.format_health_table import format_health_table
from ads_b.reporting.read_health_history import read_health_history
from ads_b.reporting.rollup_health_history import rollup_health_history
from ads_b.reporting.write_health_history_chart import write_health_history_chart
from ads_b.reporting.write_health_history_csv import write_health_history_csv

logger = logging.getLogger(__name__)


def report_health_history(
    health_log_path: str,
    csv_path: str | None,
    out_path: str | None,
    out_stream: TextIO = sys.stdout,
) -> list[dict]:
    """Read a JSONL health-history log and report per-day metrics.

    Always writes a text table to out_stream. Writes a CSV when csv_path is
    given, and a lines-per-day PNG when out_path is given.

    Args:
        health_log_path: Path to the JSONL health-history file.
        csv_path: Optional path to also write per-day rows as CSV.
        out_path: Optional path to also write a lines-per-day PNG chart.
        out_stream: Where the text table is written (defaults to stdout;
            injectable for tests).

    Returns:
        The per-day rollup rows.
    """
    # Parse the file, surfacing any skipped (corrupt) lines through the log.
    records: list[dict]
    skipped: int
    records, skipped = read_health_history(health_log_path)
    if skipped:
        logger.warning(f'Skipped {skipped} unparseable line(s) in {health_log_path}')

    # Roll up into per-day rows.
    rows: list[dict] = rollup_health_history(records)

    # Always write the text table to the output stream (program output).
    out_stream.write(format_health_table(rows))

    # Optional CSV output.
    if csv_path is not None:
        write_health_history_csv(rows, csv_path)

    # Optional PNG chart.
    if out_path is not None:
        write_health_history_chart(rows, out_path)

    return rows
