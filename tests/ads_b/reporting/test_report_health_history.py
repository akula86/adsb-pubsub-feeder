import io
import json
from pathlib import Path

from ads_b.reporting.report_health_history import report_health_history


def _write_jsonl(path: Path, records: list[dict]) -> None:
    """Write records as JSONL, plus one deliberately corrupt trailing line."""
    lines = [json.dumps(r) for r in records]
    lines.append('{not valid json')  # a crash-truncated final line
    path.write_text('\n'.join(lines) + '\n')


def test_reads_jsonl_and_rolls_up_per_day(tmp_path: Path) -> None:
    """The CLI parses JSONL (skipping bad lines), writes the table, returns rows."""
    log = tmp_path / 'history.log'
    run = '2026-07-14T00:00:00+00:00'
    _write_jsonl(
        log,
        [
            {'ts': '2026-07-14T00:05:00+00:00', 'started_at': run,
             'lines_this_interval': 500, 'uptime_seconds': 300,
             'disconnects': 0, 'publishes_failed': 0},
            {'ts': '2026-07-14T00:10:00+00:00', 'started_at': run,
             'lines_this_interval': 700, 'uptime_seconds': 600,
             'disconnects': 0, 'publishes_failed': 0},
        ],
    )
    stream = io.StringIO()

    rows = report_health_history(
        str(log), csv_path=None, out_path=None, out_stream=stream
    )

    assert len(rows) == 1
    assert rows[0]['day'] == '2026-07-14'
    assert rows[0]['lines'] == 1200
    # The text table was written to the injected stream.
    out = stream.getvalue()
    assert '2026-07-14' in out
    assert '1,200' in out


def test_writes_csv(tmp_path: Path) -> None:
    """With csv_path set, a CSV of the rows is written."""
    log = tmp_path / 'history.log'
    csv_path = tmp_path / 'daily.csv'
    run = '2026-07-14T00:00:00+00:00'
    _write_jsonl(
        log,
        [{'ts': '2026-07-14T00:05:00+00:00', 'started_at': run,
          'lines_this_interval': 500, 'uptime_seconds': 300,
          'disconnects': 0, 'publishes_failed': 0}],
    )

    report_health_history(
        str(log), csv_path=str(csv_path), out_path=None, out_stream=io.StringIO()
    )

    text = csv_path.read_text()
    assert 'day' in text
    assert '2026-07-14' in text
    assert '500' in text
