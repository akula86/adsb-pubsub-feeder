from pathlib import Path

import pytest

from ads_b.config.read_credentials_path import read_credentials_path


def test_reads_credential_path(tmp_path: Path) -> None:
    """The credential path is read from a plain KEY=value line."""
    env_path = tmp_path / '.env'
    env_path.write_text('GOOGLE_APPLICATION_CREDENTIALS=/opt/adsb/service-account.json\n')

    assert read_credentials_path(env_path) == '/opt/adsb/service-account.json'


def test_ignores_comments_blanks_and_strips_quotes(tmp_path: Path) -> None:
    """Comments and blank lines are skipped, and surrounding quotes are stripped."""
    env_path = tmp_path / '.env'
    env_path.write_text('# comment\n\nGOOGLE_APPLICATION_CREDENTIALS="/tmp/sa.json"\n')

    assert read_credentials_path(env_path) == '/tmp/sa.json'


def test_missing_key_raises_key_error(tmp_path: Path) -> None:
    """A .env without the credential key raises KeyError."""
    env_path = tmp_path / '.env'
    env_path.write_text('OTHER=value\n')

    with pytest.raises(KeyError):
        read_credentials_path(env_path)
