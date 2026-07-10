import logging
from concurrent.futures import Future

from ads_b.publish.publisher_like import PublisherLike

logger = logging.getLogger(__name__)


def publish_line(publisher: PublisherLike, topic_path: str, line: str) -> Future:
    """Publish one SBS line as a single Pub/Sub message.

    Args:
        publisher: A Pub/Sub publisher client exposing publish(topic, data).
        topic_path: The fully-qualified topic path (projects/.../topics/...).
        line: The single SBS line to publish.

    Returns:
        The publish Future returned by the client.
    """
    # Encode the line to UTF-8 bytes for the message body.
    data: bytes = line.encode('utf-8')
    # Publish and return the future so the caller can reconcile it later.
    return publisher.publish(topic_path, data)
