import argparse

from ads_b.reporting.report_health_history import report_health_history


def main() -> None:
    """Parse arguments and run the health-history report."""
    # CLI: required log path, optional CSV and PNG outputs.
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description='Report per-day metrics from the health-history JSONL log.'
    )
    parser.add_argument('--health-log', required=True, help='Path to the JSONL log')
    parser.add_argument('--csv', default=None, help='Optional CSV output path')
    parser.add_argument('--out', default=None, help='Optional PNG chart output path')
    args: argparse.Namespace = parser.parse_args()

    # Run the report, letting the table go to stdout by default.
    report_health_history(args.health_log, args.csv, args.out)


if __name__ == '__main__':
    main()
