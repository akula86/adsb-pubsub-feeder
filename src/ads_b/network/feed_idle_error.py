class FeedIdleError(Exception):
    """Raised when no bytes arrive from the feed within the idle timeout."""
