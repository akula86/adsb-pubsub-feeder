import logging
import socket
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future
from datetime import datetime, timezone
from functools import partial

from ads_b.network.close_socket import close_socket
from ads_b.config.config_model import Config
from ads_b.network.connect_with_backoff import connect_with_backoff
from ads_b.publish.drain_futures import drain_futures
from ads_b.network.feed_idle_error import FeedIdleError
from ads_b.health.feeder_stats import FeederStats
from ads_b.publish.publish_line import publish_line
from ads_b.publish.publish_line_like import PublishLineLike
from ads_b.publish.publisher_like import PublisherLike
from ads_b.network.read_sbs_lines import read_sbs_lines
from ads_b.publish.reconcile_futures import reconcile_futures
from ads_b.health.safe_write_health_file import safe_write_health_file
from ads_b.observability.throttled_logger import ThrottledLogger

logger = logging.getLogger(__name__)

# Maximum time to wait for outstanding publishes to settle during shutdown.
DRAIN_TIMEOUT_SECONDS = 5.0


def run_feeder(
    config: Config,
    publisher: PublisherLike,
    topic_path: str,
    connect: Callable[..., socket.socket | None] = connect_with_backoff,
    read_lines: Callable[..., Iterator[str | None]] = read_sbs_lines,
    publish: PublishLineLike = publish_line,
    should_continue: Callable[[], bool] = lambda: True,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = partial(datetime.now, timezone.utc),
    drain_timeout_seconds: float = DRAIN_TIMEOUT_SECONDS,
) -> None:
    """Read the SBS feed and publish one message per line until stopped.

    Each complete line is published immediately as its own Pub/Sub message; the
    SDK batches messages on the wire. The read socket recv timeout is
    ``health_tick_seconds``, so the reader yields a None tick at least that often
    even on a quiet feed, driving the periodic health write, the idle watchdog,
    and the shutdown check. A health file is written every ``write_interval_seconds``
    and once more on shutdown.

    Args:
        config: Resolved feeder configuration.
        publisher: Pub/Sub publisher client exposing
            publish(topic, data, **attrs).
        topic_path: Fully-qualified Pub/Sub topic path.
        connect: Injectable connector (defaults to connect_with_backoff).
        read_lines: Injectable line reader (defaults to read_sbs_lines).
        publish: Injectable single-line publisher (defaults to publish_line);
            called as publish(publisher, topic_path, line, location).
        should_continue: Returns False to request graceful shutdown.
        monotonic: Injectable monotonic clock (defaults to time.monotonic).
        now: Injectable wall clock returning aware UTC datetimes.
        drain_timeout_seconds: Max time to wait for publishes on shutdown.
    """
    # Outstanding publish futures, and the stats snapshotted into the health file.
    pending: list[Future] = []
    stats: FeederStats = FeederStats(started_at=now())
    # Throttle for flood-prone errors (publish failures, health-write failures).
    throttle: ThrottledLogger = ThrottledLogger(
        logger,
        config.error_sample_count,
        config.error_summary_interval_seconds,
        monotonic,
    )
    # Monotonic marker for the periodic health-write deadline.
    last_health_write: float = monotonic()

    # should_continue() is polled once before the first connect, once per read
    # event (line or idle tick), and once more after an error-driven reconnect.
    keep_going: bool = should_continue()
    reconnect_pending: bool = False
    while keep_going:
        # Connect with the recv timeout set to the health tick, plus keepalive.
        # connect polls should_continue during its backoff, so a shutdown while
        # the feed is down returns None instead of blocking.
        sock: socket.socket | None = connect(
            config.feed_host,
            config.feed_port,
            config.health_tick_seconds,
            config.initial_backoff_seconds,
            config.max_backoff_seconds,
            config.keepalive_idle_seconds,
            config.keepalive_interval_seconds,
            config.keepalive_max_fails,
            should_continue,
        )
        # None means a shutdown was requested while retrying a down feed.
        if sock is None:
            break
        stats.record_connect()

        # After an error-driven reconnect, confirm we should still continue
        # before reading from the freshly (re)opened connection.
        if reconnect_pending:
            keep_going = should_continue()
            reconnect_pending = False
            if not keep_going:
                close_socket(sock)
                break

        try:
            # Inner loop: consume lines (and idle ticks) from the reader.
            for line_or_tick in read_lines(
                sock, config.feed_idle_timeout_seconds, monotonic
            ):
                # A real line is published immediately as one message; None is
                # an idle tick that only services the timers below.
                if line_or_tick is not None:
                    # Bound the backlog: if full, shed the oldest (stalest)
                    # publish before tracking the new one. A live ADS-B position
                    # goes stale in seconds, so newest data is most valuable.
                    if len(pending) >= config.max_pending:
                        oldest: Future = pending.pop(0)
                        oldest.cancel()  # best-effort; an already-sent won't cancel
                        stats.record_dropped(1)
                    pending.append(
                        publish(publisher, topic_path, line_or_tick, config.location)
                    )
                    stats.record_publish(now())

                # Reconcile completed futures without blocking; fold outcomes in.
                reconciled = reconcile_futures(pending)
                pending[:] = reconciled.still_pending
                stats.record_publish_results(
                    reconciled.resolved,
                    reconciled.failed,
                    reconciled.last_error,
                    now(),
                )
                # Log publish failures through the throttle (once per reconcile
                # pass that had failures, with the batch count), so a failing
                # backlog cannot flood the log.
                if reconciled.failed > 0:
                    throttle.error(
                        'publish_failed',
                        f'{reconciled.failed} publish(es) failed: {reconciled.last_error}',
                    )

                # At the UTC-day boundary, log the day's totals then reset the
                # cumulative counters. Runs on every read event so even an idle
                # tick catches midnight within about one health tick.
                rolled = stats.roll_over_if_new_day(now(), len(pending))
                if rolled is not None:
                    logger.info(f'Daily totals at UTC midnight: {rolled}')

                # Periodic health write, gated behind the write interval.
                if monotonic() - last_health_write >= config.write_interval_seconds:
                    safe_write_health_file(
                        config.health_file_path,
                        stats,
                        now(),
                        config.write_interval_seconds,
                        len(pending),
                        throttle,
                    )
                    last_health_write = monotonic()

                # Honour a shutdown request between read events.
                keep_going = should_continue()
                if not keep_going:
                    break
            else:
                # The reader exhausted without raising or being told to stop
                # (only possible with a finite fake reader in tests, since the
                # real reader loops forever); treat that as end of feed.
                keep_going = False
        except (ConnectionError, FeedIdleError) as error:
            # Feed dropped or went silent; record it and reconnect on the next pass.
            logger.warning(f'Feed interrupted ({error}); reconnecting')
            stats.record_disconnect(now())
            reconnect_pending = True
        finally:
            # Always close the socket before reconnecting or exiting.
            close_socket(sock)

    # Graceful shutdown: drain outstanding publishes, fold their outcomes into
    # stats, then write the final health file so it reflects the drain.
    drained = drain_futures(pending, drain_timeout_seconds)
    stats.record_publish_results(
        drained.resolved, drained.failed, drained.last_error, now()
    )
    if drained.failed > 0:
        throttle.error(
            'publish_failed',
            f'{drained.failed} publish(es) failed during drain: {drained.last_error}',
        )
    safe_write_health_file(
        config.health_file_path,
        stats,
        now(),
        config.write_interval_seconds,
        len(drained.still_pending),
        throttle,
    )
    logger.info('Feeder stopped')
