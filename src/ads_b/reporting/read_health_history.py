import json
import logging

logger = logging.getLogger(__name__)


def read_health_history(health_log_path: str) -> tuple[list[dict], int]:
    """Parse a JSONL health-history file into records, tolerating bad lines.

    Blank lines are ignored; any line that fails to parse as JSON (for example a
    crash-truncated final line) is skipped and counted rather than aborting the
    whole report.

    Args:
        health_log_path: Path to the JSONL health-history file.

    Returns:
        A tuple of (parsed records, count of unparseable lines skipped).
    """
    # Parse line by line so a single corrupt line cannot lose the whole file.
    records: list[dict] = []
    skipped: int = 0
    with open(health_log_path, encoding='utf-8') as handle:
        for line in handle:
            # Ignore blank lines outright.
            stripped: str = line.strip()
            if not stripped:
                continue
            # Skip and count anything that is not valid JSON.
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError:
                skipped += 1
    return records, skipped
