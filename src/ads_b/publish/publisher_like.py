from concurrent.futures import Future
from typing import Protocol


class PublisherLike(Protocol):
    """Minimal interface required from a Pub/Sub publisher client."""

    def publish(self, topic: str, data: bytes, **attrs: str) -> Future:
        """Publish raw bytes with optional attributes and return a future."""
        ...
