import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# The environment variable in ~/.env that names the service-account key file.
CREDENTIALS_ENV_KEY = 'GOOGLE_APPLICATION_CREDENTIALS'


def read_credentials_path(env_path: Path) -> str:
    """Read the credential file path from a simple KEY=value .env file.

    Args:
        env_path: Path to the ~/.env-style file.

    Returns:
        The value of GOOGLE_APPLICATION_CREDENTIALS with surrounding quotes stripped.

    Raises:
        KeyError: If the credential key is not present in the file.
    """
    # Parse the .env line by line, skipping comments and blanks.
    for raw_line in env_path.read_text().splitlines():
        # Normalise whitespace so a leading/trailing space never hides a match.
        line: str = raw_line.strip()
        # Skip blank lines, comment lines, and lines without a key=value shape.
        if not line or line.startswith('#') or '=' not in line:
            continue
        # Split on the first '=' so values containing '=' survive intact.
        key, _, value = line.partition('=')
        if key.strip() == CREDENTIALS_ENV_KEY:
            # Strip surrounding single or double quotes from the value.
            return value.strip().strip('"').strip("'")
    # No matching key means the caller cannot authenticate; fail loudly.
    raise KeyError(f'{CREDENTIALS_ENV_KEY} not found in {env_path}')
