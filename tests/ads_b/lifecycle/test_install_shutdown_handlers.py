import signal

from ads_b.lifecycle.install_shutdown_handlers import install_shutdown_handlers
from ads_b.lifecycle.shutdown_flag import ShutdownFlag


def test_registers_sigint_and_sigterm_that_set_the_flag() -> None:
    """The installed handlers set the flag when invoked, for both signals."""
    # Save the current handlers so the test can restore them afterwards.
    original_int = signal.getsignal(signal.SIGINT)
    original_term = signal.getsignal(signal.SIGTERM)
    try:
        flag = ShutdownFlag()
        install_shutdown_handlers(flag)

        # Invoke the registered SIGINT handler directly (no real signal sent).
        handler_int = signal.getsignal(signal.SIGINT)
        assert callable(handler_int)
        handler_int(signal.SIGINT, None)
        assert flag.is_requested() is True

        # A fresh flag confirms the SIGTERM handler flips it too.
        flag2 = ShutdownFlag()
        install_shutdown_handlers(flag2)
        handler_term = signal.getsignal(signal.SIGTERM)
        assert callable(handler_term)
        handler_term(signal.SIGTERM, None)
        assert flag2.is_requested() is True
    finally:
        # Restore the original signal handlers.
        signal.signal(signal.SIGINT, original_int)
        signal.signal(signal.SIGTERM, original_term)
