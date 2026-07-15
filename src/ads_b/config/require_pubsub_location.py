import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# The unedited placeholder shipped in the app.toml template; a real deployment
# must replace it, so treat it as "not configured" rather than a valid value.
LOCATION_PLACEHOLDER = 'CHANGE_ME_LOCATION'

# Pub/Sub caps each message attribute value at 1024 bytes; a longer value is
# rejected by the service at publish time, so fail fast at config load instead.
MAX_ATTRIBUTE_VALUE_BYTES = 1_024


def require_pubsub_location(raw: dict, app_toml_path: Path) -> str:
    """Extract and validate the feeder location from parsed app.toml contents.

    The location is the IATA code of the nearest airport (e.g. SJC), published
    as a message attribute on every Pub/Sub message, so an absent, empty, or
    unedited-placeholder value would silently mis-tag all downstream data. This
    fails loudly at load time with a message that names the file and section an
    operator must fix.

    Args:
        raw: The parsed app.toml contents as nested dicts.
        app_toml_path: Path to the app.toml file, named in error messages.

    Returns:
        The normalised (stripped, uppercased) location code.

    Raises:
        ValueError: If the [pubsub] location key is missing, blank, still set
            to the template placeholder, or longer than the 1024-byte Pub/Sub
            attribute-value limit.
    """
    # Read the [pubsub] section, defaulting to empty so a missing section
    # produces the same clear error as a missing key rather than a KeyError.
    pubsub: dict = raw.get('pubsub', {})
    raw_location = pubsub.get('location')

    # A missing key means the config predates this requirement (or the section
    # is absent); point the operator at the exact file and section to edit.
    if raw_location is None:
        raise ValueError(
            f"missing 'location' in the [pubsub] section of {app_toml_path}; "
            f'add e.g. location = "SJC"'
        )

    # Normalise before validating so surrounding whitespace never hides an
    # otherwise-blank value, and casing is consistent on the wire.
    location: str = str(raw_location).strip().upper()

    # An empty value or the unedited template placeholder is not a real
    # location; reject both with the same actionable message.
    if not location or location == LOCATION_PLACEHOLDER:
        raise ValueError(
            f"'location' in the [pubsub] section of {app_toml_path} is unset "
            f'or still the template placeholder; set it to the feeder code, '
            f'e.g. location = "SJC"'
        )

    # Pub/Sub rejects an attribute value over 1024 bytes; measure encoded bytes
    # (not characters) since a multibyte value can exceed the cap while short.
    value_bytes: int = len(location.encode('utf-8'))
    if value_bytes > MAX_ATTRIBUTE_VALUE_BYTES:
        raise ValueError(
            f"'location' in the [pubsub] section of {app_toml_path} is "
            f'{value_bytes} bytes, over the {MAX_ATTRIBUTE_VALUE_BYTES}-byte '
            f'Pub/Sub attribute-value limit'
        )

    return location
