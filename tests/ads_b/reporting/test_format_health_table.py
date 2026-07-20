from ads_b.reporting.format_health_table import format_health_table


def test_table_has_header_and_a_row_with_grouped_number() -> None:
    """The table includes a header and a day row with a thousands-grouped count."""
    rows = [
        {'day': '2026-07-14', 'lines': 1200, 'uptime_seconds': 86_400,
         'disconnects': 0, 'publishes_failed': 0},
    ]

    text = format_health_table(rows)

    assert 'Day' in text
    assert '2026-07-14' in text
    # User-facing numbers use comma grouping (>= 1000).
    assert '1,200' in text
    # A full day of uptime reads as 100%.
    assert '100.0%' in text
