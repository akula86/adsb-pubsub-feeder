
class ShutdownFlag:
    """A thread/signal-safe one-way flag for requesting graceful shutdown."""

    def __init__(self) -> None:
        """Initialise the flag in the not-requested state."""
        # Once set True by request(), the flag never goes back to False.
        self._requested = False

    def request(self) -> None:
        """Mark that a shutdown has been requested."""
        # A signal handler calls this; setting a bool is atomic and safe here.
        self._requested = True

    def is_requested(self) -> bool:
        """Return True once a shutdown has been requested."""
        return self._requested
