from pathlib import Path

import pytest

from ads_b.config.require_pubsub_location import require_pubsub_location


def _path() -> Path:
    """Return an arbitrary app.toml path for error-message assertions."""
    return Path('/etc/adsb/app.toml')


def test_returns_location_when_present() -> None:
    """A valid location is returned unchanged when already normalised."""
    raw = {'pubsub': {'location': 'SJC'}}

    assert require_pubsub_location(raw, _path()) == 'SJC'


def test_strips_and_uppercases() -> None:
    """Surrounding whitespace is stripped and the value is uppercased."""
    raw = {'pubsub': {'location': '  sjc  '}}

    assert require_pubsub_location(raw, _path()) == 'SJC'


def test_missing_key_raises_valueerror_naming_file() -> None:
    """A missing location key raises ValueError naming the file and section."""
    raw = {'pubsub': {'project_id': 'p'}}

    with pytest.raises(ValueError) as excinfo:
        require_pubsub_location(raw, _path())

    assert 'location' in str(excinfo.value)
    assert '/etc/adsb/app.toml' in str(excinfo.value)


def test_missing_pubsub_section_raises_valueerror() -> None:
    """An absent [pubsub] section fails the same way as a missing key."""
    raw: dict = {}

    with pytest.raises(ValueError):
        require_pubsub_location(raw, _path())


def test_empty_value_raises_valueerror() -> None:
    """A blank or whitespace-only location is rejected."""
    raw = {'pubsub': {'location': '   '}}

    with pytest.raises(ValueError):
        require_pubsub_location(raw, _path())


def test_placeholder_value_raises_valueerror() -> None:
    """The unedited template placeholder is rejected, case-insensitively."""
    raw = {'pubsub': {'location': 'change_me_location'}}

    with pytest.raises(ValueError):
        require_pubsub_location(raw, _path())


def test_value_over_1024_bytes_raises_valueerror() -> None:
    """A location exceeding the 1024-byte Pub/Sub attribute limit is rejected."""
    raw = {'pubsub': {'location': 'A' * 1_025}}

    with pytest.raises(ValueError):
        require_pubsub_location(raw, _path())


def test_value_at_1024_bytes_is_accepted() -> None:
    """A location exactly at the 1024-byte limit is accepted (boundary)."""
    raw = {'pubsub': {'location': 'A' * 1_024}}

    assert require_pubsub_location(raw, _path()) == 'A' * 1_024
