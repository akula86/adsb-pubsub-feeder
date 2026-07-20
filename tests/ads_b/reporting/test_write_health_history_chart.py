from pathlib import Path

import pytest

from ads_b.reporting.write_health_history_chart import write_health_history_chart


def test_writes_png_when_matplotlib_available(tmp_path: Path) -> None:
    """A non-empty PNG is produced from per-day rows (skipped without matplotlib)."""
    # matplotlib is an optional dependency (absent on the Pi's text/CSV path);
    # skip cleanly when it is not installed rather than fail the suite.
    pytest.importorskip('matplotlib')

    out_path = tmp_path / 'daily.png'
    rows = [
        {'day': '2026-07-13', 'lines': 11_980_442, 'uptime_seconds': 86_400,
         'disconnects': 0, 'publishes_failed': 0},
        {'day': '2026-07-14', 'lines': 12_197_004, 'uptime_seconds': 86_400,
         'disconnects': 0, 'publishes_failed': 0},
    ]

    write_health_history_chart(rows, str(out_path))

    # A real PNG file was written, with the PNG magic bytes and non-zero size.
    assert out_path.exists()
    assert out_path.stat().st_size > 0
    assert out_path.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
