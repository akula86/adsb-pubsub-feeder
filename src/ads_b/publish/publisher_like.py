from concurrent.futures import Future
from typing import Protocol


class PublisherLike(Protocol):
    """Minimal interface required from a Pub/Sub publisher client."""

    def publish(self, topic: str, data: bytes) -> Future:
        """Publish raw bytes to a topic and return a future."""
        ...
