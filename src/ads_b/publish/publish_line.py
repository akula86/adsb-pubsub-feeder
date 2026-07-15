import logging
from concurrent.futures import Future

from ads_b.publish.publisher_like import PublisherLike

logger = logging.getLogger(__name__)

# Pub/Sub message attribute carrying the feeder's physical location code.
LOCATION_ATTRIBUTE = 'LOCATION'


def publish_line(
    publisher: PublisherLike, topic_path: str, line: str, location: str
) -> Future:
    """Publish one SBS line as a single Pub/Sub message tagged with a location.

    Args:
        publisher: A Pub/Sub publisher client exposing
            publish(topic, data, **attrs), where attrs become message attributes.
        topic_path: The fully-qualified topic path (projects/.../topics/...).
        line: The single SBS line to publish.
        location: The feeder location code, attached as a message attribute so
            subscribers can filter or route on it without decoding the body.

    Returns:
        The publish Future returned by the client.
    """
    # Encode the line to UTF-8 bytes for the message body.
    data: bytes = line.encode('utf-8')
    # Publish with the location as a message attribute and return the future so
    # the caller can reconcile it later.
    return publisher.publish(topic_path, data, **{LOCATION_ATTRIBUTE: location})
