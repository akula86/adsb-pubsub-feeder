from datetime import date, datetime


class FeederStats:
    """Mutable counters and timestamps describing feeder activity.

    All mutation happens on the single loop thread, so the counters are plain
    integers with no locking.
    """

    def __init__(self, started_at: datetime) -> None:
        """Initialise all counters to zero and timestamps to unset.

        Args:
            started_at: When the feeder started (used for uptime).
        """
        # Startup time, fixed for the life of the process.
        self.started_at = started_at
        # UTC date of the current counting window; advanced at each midnight rollover.
        self.current_day: date = started_at.date()
        # Counters are Python ints (arbitrary precision) — they never overflow.
        # Cumulative lines, the per-interval delta, and the message (publish) count.
        self.lines_total: int = 0
        self.lines_since_write: int = 0
        self.messages_total: int = 0
        # The last successful publish time.
        self.last_publish_at: datetime | None = None
        # Connection lifecycle counters and the last reconnect time.
        self.connects: int = 0
        self.disconnects: int = 0
        self.last_reconnect_at: datetime | None = None
        # Cumulative publish-future outcomes and the most recent failure detail.
        self.publishes_resolved: int = 0
        self.publishes_failed: int = 0
        # Publishes dropped (oldest-first) to bound the backlog under backpressure.
        self.publishes_dropped: int = 0
        self.last_failure_at: datetime | None = None
        self.last_failure: str | None = None

    def record_publish(self, now: datetime) -> None:
        """Record that one line was published as one message.

        Args:
            now: Publish time, recorded as the last publish timestamp.
        """
        # One line equals one message: grow all three counters together.
        self.lines_total += 1
        self.lines_since_write += 1
        self.messages_total += 1
        # The publish just happened, so this is the freshest publish time.
        self.last_publish_at = now

    def record_connect(self) -> None:
        """Record a successful connection to the feed."""
        self.connects += 1

    def record_disconnect(self, now: datetime) -> None:
        """Record a feed disconnect or idle-forced reconnect.

        Args:
            now: Time of the disconnect, kept as the last reconnect time.
        """
        self.disconnects += 1
        self.last_reconnect_at = now

    def record_publish_results(
        self, resolved: int, failed: int, last_error: str | None, now: datetime
    ) -> None:
        """Fold a batch of reconciled future outcomes into the counters.

        Args:
            resolved: Count of futures that completed successfully this batch.
            failed: Count of futures that completed with an exception this batch.
            last_error: str() of the most recent failure this batch, or None.
            now: Current time, recorded as last_failure_at when failed > 0.
        """
        # Grow the cumulative outcome counters.
        self.publishes_resolved += resolved
        self.publishes_failed += failed
        # Record failure detail only when this batch actually had a failure.
        if failed > 0 and last_error is not None:
            self.last_failure_at = now
            self.last_failure = last_error

    def record_dropped(self, count: int) -> None:
        """Add to the count of publish futures dropped to bound the backlog.

        Args:
            count: Number of oldest-first futures dropped this event.
        """
        self.publishes_dropped += count

    def roll_over_if_new_day(self, now: datetime, in_flight: int) -> dict | None:
        """Capture and reset the daily counters when the UTC date advances.

        On the first call whose ``now`` falls on a later UTC date than the
        current window, capture the full snapshot (for the caller to log) and
        zero the seven cumulative counters, advancing the window to the new
        day. On any call within the same UTC day, do nothing.

        Args:
            now: Current aware-UTC time; its date drives the rollover.
            in_flight: Current in-flight publish count, for the captured snapshot.

        Returns:
            The snapshot dict captured just before reset, or None if the UTC
            day has not changed.
        """
        # Same UTC day: nothing to do.
        if now.date() == self.current_day:
            return None
        # Day advanced: capture everything before zeroing, then reset the window.
        captured: dict = self.snapshot(now, in_flight)
        self.current_day = now.date()
        # Zero only the cumulative totals; deltas, timestamps, detail persist.
        self.lines_total = 0
        self.messages_total = 0
        self.connects = 0
        self.disconnects = 0
        self.publishes_resolved = 0
        self.publishes_failed = 0
        self.publishes_dropped = 0
        return captured

    def snapshot(self, now: datetime, in_flight: int) -> dict:
        """Return the current stats as a JSON-ready dict (without status).

        Args:
            now: Current time, used to compute uptime.
            in_flight: Publish futures submitted but not yet reconciled.

        Returns:
            A dict of the health payload fields except the derived status.
        """
        # Build the payload; ISO-format timestamps and null out unset ones.
        return {
            'started_at': self.started_at.isoformat(),
            'last_publish_at': (
                self.last_publish_at.isoformat()
                if self.last_publish_at is not None
                else None
            ),
            'uptime_seconds': int((now - self.started_at).total_seconds()),
            'lines_total': self.lines_total,
            'lines_last_interval': self.lines_since_write,
            'messages_total': self.messages_total,
            'connects': self.connects,
            'disconnects': self.disconnects,
            'last_reconnect_at': (
                self.last_reconnect_at.isoformat()
                if self.last_reconnect_at is not None
                else None
            ),
            'publishes_resolved': self.publishes_resolved,
            'publishes_failed': self.publishes_failed,
            'publishes_in_flight': in_flight,
            'publishes_dropped': self.publishes_dropped,
            'last_failure_at': (
                self.last_failure_at.isoformat()
                if self.last_failure_at is not None
                else None
            ),
            'last_failure': self.last_failure,
        }

    def reset_interval(self) -> None:
        """Zero the per-interval line delta after a health write."""
        self.lines_since_write = 0
