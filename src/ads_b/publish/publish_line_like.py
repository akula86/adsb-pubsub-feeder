from concurrent.futures import Future
from typing import Protocol

from ads_b.publish.publisher_like import PublisherLike


class PublishLineLike(Protocol):
    """Callable contract for the injectable single-line publisher seam.

    Declaring the full four-argument signature (rather than Callable[..., Future])
    lets mypy reject an injected publisher wired to an out-of-date arity at the
    call site, instead of failing with a TypeError on the first published line.
    """

    def __call__(
        self,
        publisher: PublisherLike,
        topic_path: str,
        line: str,
        location: str,
    ) -> Future:
        """Publish one line and return the publish future."""
        ...
