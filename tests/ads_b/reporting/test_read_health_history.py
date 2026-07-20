import json
from pathlib import Path

from ads_b.reporting.read_health_history import read_health_history


def test_parses_records_and_counts_skipped(tmp_path: Path) -> None:
    """Valid JSONL lines are parsed; a corrupt line is skipped and counted."""
    log = tmp_path / 'history.log'
    good = {'ts': '2026-07-14T00:05:00+00:00', 'lines_this_interval': 500}
    # Two good lines, one blank (ignored), one corrupt (skipped + counted).
    log.write_text(json.dumps(good) + '\n\n' + json.dumps(good) + '\n{bad\n')

    records, skipped = read_health_history(str(log))

    assert len(records) == 2
    assert records[0] == good
    assert skipped == 1
