from ads_b.lifecycle.shutdown_flag import ShutdownFlag


def test_starts_not_requested() -> None:
    """A fresh flag reports no shutdown requested."""
    flag = ShutdownFlag()

    assert flag.is_requested() is False


def test_request_sets_the_flag() -> None:
    """request() flips the flag to the requested state permanently."""
    flag = ShutdownFlag()

    flag.request()

    assert flag.is_requested() is True
