from ads_b.publish.publish_line import publish_line


class FakeFuture:
    """A stand-in for a Pub/Sub publish future."""


class FakePublisher:
    """A fake Pub/Sub publisher recording publish() calls."""

    def __init__(self) -> None:
        """Initialise the recorded-calls list."""
        self.calls: list[tuple[str, bytes, dict[str, str]]] = []

    def publish(self, topic_path: str, data: bytes, **attrs: str) -> FakeFuture:
        """Record the call (with attributes) and return a fake future."""
        self.calls.append((topic_path, data, attrs))
        return FakeFuture()


def test_publishes_one_line_as_utf8_bytes_with_location_attribute() -> None:
    """publish_line publishes the UTF-8 bytes tagged with the LOCATION attribute."""
    publisher = FakePublisher()

    future = publish_line(publisher, 'projects/p/topics/t', 'MSG,3,1,1,ABC', 'SJC')

    assert isinstance(future, FakeFuture)
    assert publisher.calls == [
        ('projects/p/topics/t', b'MSG,3,1,1,ABC', {'LOCATION': 'SJC'})
    ]
