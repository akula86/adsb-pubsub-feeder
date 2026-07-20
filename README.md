# ads-b

Forward the fr24feed BaseStation (SBS) feed on TCP port 30003 to a Google Cloud
Pub/Sub topic, one SBS line per message. Designed to run unattended on a
Raspberry Pi (also tested on macOS).

This is a Python application that uses `uv` for dependency management.

## Setup

Steps assume you are logged into the Pi. They also assume that in GCP:

- you have created a service account
- you have enabled the Pub/Sub API in your project
- the topic owner has granted "Pub/Sub Publisher" to your service account for the target topic

For macOS, use `mac.app.toml` instead of `pi.app.toml` in the steps below (its
paths use `/tmp`, which always exists, so no runtime directory is needed).

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Installs the `uv` Python package/venv manager. Restart your shell (or
`source ~/.bashrc`) so `uv` is on `PATH`.

### 2. Clone the repo and install dependencies

```bash
cd ~
mkdir GitHub
cd GitHub
git clone https://github.com/akula86/adsb-pubsub-feeder.git
cd adsb-pubsub-feeder
uv sync
```

Clones into `./adsb-pubsub-feeder` and installs `google-cloud-pubsub` plus the
test tooling into a project-local `.venv`. Run the remaining steps from this
directory.

### 3. Create the runtime directory

```bash
sudo mkdir -p /opt/adsb && sudo chown "$(whoami)" /opt/adsb
```

Holds the service-account key, health file, and log. The directory is NOT
created for you — the feeder exits at startup with a `FileNotFoundError` if the
health/log directory is missing. (Not needed on macOS, where `mac.app.toml` uses
`/tmp`.)

### 4. Set the credential path in ~/.env

The service-account key path is a secret and lives in `~/.env`, never in the
config file or the code:

```bash
echo 'GOOGLE_APPLICATION_CREDENTIALS=/opt/adsb/service-account.json' >> ~/.env
```

Then place your key file at that path and restrict it to owner-only:

```bash
chmod 600 /opt/adsb/service-account.json
```

The feeder reads this path at startup and authenticates the Pub/Sub client
directly from the key file — it does not rely on the environment variable being
exported. Override the `.env` location with `--env /path/to/.env` if needed.

### 5. Create your config from the template

`app.toml` is a tracked template with placeholder values. Copy it to a real,
gitignored config and fill in your deployment's values:

```bash
cp app.toml pi.app.toml
```

Edit `pi.app.toml` and replace every `CHANGE_ME_*` placeholder — at least
`[feed] host`, `[pubsub] project_id`, `topic_id`, and `location`, and the
`[health]` / `[logging]` file paths. The credential path is NOT in this file;
it comes from `~/.env`.

To protect resources on the Pi, logging rotates the file after it reaches 5 MB
and keeps only three log files, and repeated errors are batched so a recurring
failure does not swamp the log. The health file is overwritten each write to
keep its size small.

Example `pi.app.toml` with placeholder values filled in:

```toml
[feed]
host = "192.168.1.50"          # your fr24feed / dump1090 host
port = 30003

[pubsub]
project_id = "my-gcp-project"
topic_id = "adsb-topic"
location = "SJC"                 # IATA code of nearest airport, sent as a LOCATION attribute

[reconnect]
initial_backoff_seconds = 1.0
max_backoff_seconds = 30.0

[watchdog]
feed_idle_timeout_seconds = 60.0

[keepalive]
idle_seconds = 1
interval_seconds = 3
max_fails = 5

[health]
health_file_path = "/opt/adsb/health.json"
write_interval_seconds = 300.0
health_tick_seconds = 1.0
health_log_file_path = "/opt/adsb/health-history.log"
health_log_max_megabytes = 5
health_log_backup_count = 3

[logging]
log_file_path = "/opt/adsb/adsb.log"
max_megabytes = 5
backup_count = 3
error_sample_count = 5
error_summary_interval_seconds = 60.0

[publish]
max_pending = 1000
```

## Run the Feeder

Once setup is complete, start the feeder.

Once you confirm it is working properly, you can configure it to run unattended
(and restart automatically after a reboot) under systemd. See
[Running as a service](#running-as-a-service).

### Start the feeder

```bash
uv run ads-b --app-toml pi.app.toml
```

Connects to the feed and publishes each complete SBS line as its own Pub/Sub
message. Ctrl-C shuts down cleanly (it drains outstanding publishes first). Run
the tests any time with `uv run pytest`.

### Tail the log

```bash
# Follow the log live — Ctrl-C stops watching, NOT the feeder
tail -f /opt/adsb/adsb.log
```

Shows connects, reconnects, and any throttled errors as they happen. A healthy
feeder logs the "Connected to feed" line on startup, then stays quiet unless
something changes.

### Check the health file

```bash
# Snapshot the current health/liveness stats
cat /opt/adsb/health.json
```

The health file is (over)written every `write_interval_seconds` from your config
(the template default is `300.0` — 5 minutes) and once more on shutdown. On a
fresh start it will not exist until the first interval elapses — wait up to
`write_interval_seconds`, or stop the feeder (Ctrl-C) to force a final write.
Lower `write_interval_seconds` (e.g. `10.0`) temporarily for faster feedback
while setting up.

Look for `"status": "healthy"` and `messages_total` / `publishes_resolved`
climbing between checks — that confirms messages are actually reaching Pub/Sub,
not just that the process is up. See [Health file](#health-file) for what every
field means.

## How it works

- Reads newline-delimited SBS lines from the feed over TCP (raw passthrough, no
  parsing). A partial line straddling reads is reassembled; the first partial
  line after each connect is discarded.
- Publishes each complete line as its own Pub/Sub message. The `google-cloud-pubsub`
  client batches messages on the wire (its defaults group up to 100 messages or
  10ms of traffic per request), so no application-level buffering is needed.
- Publish futures are reconciled without blocking the read loop; the backlog is
  capped (oldest dropped when full) and repeated failures are throttled in the
  log rather than flooded.
- Applies TCP keepalive after connecting so a dead peer is detected at the OS
  layer, and auto-reconnects with exponential backoff if the feed drops.
- Forces a reconnect if the feed goes silent past the idle timeout (default 60s).
- Writes a periodic JSON health file (see below) and drains outstanding
  publishes on SIGINT/SIGTERM.

## Health file

The feeder writes a small JSON health file (default `/opt/adsb/health.json`)
every `write_interval_seconds` and once on shutdown, overwriting it each time so
it never grows. It is the feeder's liveness signal for monitoring:

```json
{
  "status": "healthy",
  "started_at": "2026-07-10T18:00:00+00:00",
  "last_publish_at": "2026-07-10T18:34:58+00:00",
  "uptime_seconds": 2098,
  "lines_total": 419600,
  "lines_last_interval": 60012,
  "messages_total": 419600,
  "connects": 1,
  "disconnects": 0,
  "last_reconnect_at": null,
  "publishes_resolved": 419583,
  "publishes_failed": 0,
  "publishes_in_flight": 17,
  "publishes_dropped": 0,
  "last_failure_at": null,
  "last_failure": null
}
```

`status` is `healthy` when a publish happened within twice the write interval,
otherwise `stale`. The write is atomic, so a reader never sees a partial file.

`messages_total` counts messages *submitted* to Pub/Sub; the delivery fields
track their *confirmed* outcome so you can tell whether messages are actually
being consumed:

| Field                 | Meaning                                                        |
| --------------------- | -------------------------------------------------------------- |
| `publishes_resolved`  | Messages Pub/Sub acknowledged. Should track `messages_total`.  |
| `publishes_failed`    | Messages that completed with a publish error.                  |
| `publishes_in_flight` | Submitted but not yet acknowledged — the current backlog.      |
| `publishes_dropped`   | Oldest publishes shed to bound the backlog under backpressure. |
| `last_failure_at`     | Timestamp of the most recent publish failure, or `null`.       |
| `last_failure`        | Message of the most recent publish failure, or `null`.         |

A healthy feed keeps `publishes_in_flight` in the single-to-low-double digits
and `publishes_resolved` close to `messages_total`. A climbing `in_flight` with
`resolved` falling behind means Pub/Sub is not keeping up — the backlog is
growing.

To keep a Pub/Sub backup from accumulating unbounded outstanding publishes, the
feeder caps the backlog at `[publish] max_pending`. When full, it sheds the
oldest (stalest) publish before accepting the next line — a live ADS-B position
goes stale within seconds, so the newest data is the most valuable to keep — and
counts each shed message in `publishes_dropped`. The feed never blocks; once
Pub/Sub recovers, the cap simply stops being hit. A nonzero and rising
`publishes_dropped` means the feeder is actively shedding load.

At UTC midnight the seven cumulative counters — `lines_total`, `messages_total`,
`connects`, `disconnects`, `publishes_resolved`, `publishes_failed`, and
`publishes_dropped` — reset to zero, so the health file shows per-day totals. The
full day's totals are written to the log as one INFO line just before the reset,
giving a daily record. `uptime_seconds`, `started_at`, and the `last_*`
timestamps are process-lifetime and do not reset.

Alongside the overwritten health file, the feeder also appends one JSONL record
per write interval to a separate rotating health-history log, configured by
`health_log_file_path`, `health_log_max_megabytes`, and `health_log_backup_count`
(same rotation shape as `[logging]`). This history is what the reporting script
below reads.

## Reporting

Summarise per-day activity from the health-history log:

```
uv run src/ads_b/reporting/report_health_history_cli.py --health-log /opt/adsb/health-history.log
```

Add `--csv daily.csv` to write a CSV, or `--out daily.png` to also render a
lines-per-day chart (the chart needs matplotlib; the text and CSV output do not,
so the Pi can run the report with no extra dependency).

## Configuration

`app.toml` holds all non-secret config:

| Section       | Key                                                                           | Meaning                                                                                                                  |
| ------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `[feed]`      | `host`, `port`                                                                | fr24feed BaseStation TCP endpoint                                                                                        |
| `[pubsub]`    | `project_id`, `topic_id`, `location`                                          | Destination Pub/Sub topic; `location` is the IATA code of the nearest airport, sent as a `LOCATION` message attribute    |
| `[reconnect]` | `initial_backoff_seconds`                                                     | First reconnect delay                                                                                                    |
| `[reconnect]` | `max_backoff_seconds`                                                         | Reconnect delay ceiling                                                                                                  |
| `[watchdog]`  | `feed_idle_timeout_seconds`                                                   | Force reconnect after this silent gap                                                                                    |
| `[keepalive]` | `idle_seconds`                                                                | Idle time before the first keepalive probe                                                                               |
| `[keepalive]` | `interval_seconds`                                                            | Interval between keepalive probes                                                                                        |
| `[keepalive]` | `max_fails`                                                                   | Unanswered probes before the peer is dropped                                                                             |
| `[health]`    | `health_file_path`                                                            | Where to write the JSON health file                                                                                      |
| `[health]`    | `write_interval_seconds`                                                      | How often to write the health file                                                                                       |
| `[health]`    | `health_tick_seconds`                                                         | Loop tick / socket recv timeout                                                                                          |
| `[health]`    | `health_log_file_path`, `health_log_max_megabytes`, `health_log_backup_count` | `health_log_*` configure a separate rotating JSONL log written once per write interval, consumed by the reporting script |
| `[publish]`   | `max_pending`                                                                 | Backlog cap; drop oldest publish when reached                                                                            |
| `[logging]`   | `error_sample_count`                                                          | Full-detail error lines before throttling                                                                                |
| `[logging]`   | `error_summary_interval_seconds`                                              | How often to log a suppressed-error summary                                                                              |

The credential path (`GOOGLE_APPLICATION_CREDENTIALS`) comes from `~/.env`, never
from `app.toml` or the code.

## Running as a service

Run under systemd so the feeder starts on boot and restarts on a crash. The app
reconnects to the feed internally and drains publishes on shutdown, so systemd
only needs to restart it if the process dies. Point your monitoring at the
health file to alert on a `stale` status or a missing `last_publish_at`.

The examples below assume the Pi conventions used elsewhere in this README: user
`pi`, repo at `/home/pi/GitHub/adsb-pubsub-feeder`, and `uv` at
`/home/pi/.local/bin/uv`. Confirm your own values first:

```bash
whoami            # the User= value
which uv          # the full ExecStart uv path (systemd has a minimal PATH)
pwd               # run from the repo; this is WorkingDirectory=
```

### 1. Create the unit file

```bash
sudo nano /etc/systemd/system/adsb-feeder.service
```

Paste the following, substituting your user and paths:

```ini
[Unit]
Description=ADS-B SBS to Google Pub/Sub feeder
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/GitHub/adsb-pubsub-feeder
ExecStart=/home/pi/.local/bin/uv run ads-b --app-toml pi.app.toml
Restart=always
RestartSec=5
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
```

Key points:

- `User=pi` (not root) so `~/.env` resolves to `/home/pi/.env`, where the
  credential path lives. Running as root would look in `/root/.env` and fail
  authentication.
- `ExecStart` uses the **full path** to `uv` — systemd runs with a minimal
  `PATH` and will not find `uv` on its own.
- `WorkingDirectory` must be the repo so `uv run` finds the project's `.venv`
  and the relative `--app-toml pi.app.toml` resolves.
- `Restart=always` handles crashes; `enable` (below) handles boot.

### 2. Enable and start it

First stop any feeder you are running by hand (Ctrl-C) so you do not
double-publish, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable adsb-feeder     # start on every boot
sudo systemctl start adsb-feeder      # start it now
```

### 3. Verify

```bash
systemctl status adsb-feeder          # expect "active (running)"
journalctl -u adsb-feeder -f          # follow output; Ctrl-C stops watching, not the service
```

You should see the `Connected to feed` line within a few seconds. To confirm it
survives a reboot, `sudo reboot`, then re-check `systemctl status adsb-feeder`
after the Pi comes back.

### Managing the service

```bash
sudo systemctl restart adsb-feeder    # after editing pi.app.toml
sudo systemctl stop adsb-feeder       # stop (stays stopped until you start it)
sudo systemctl disable adsb-feeder    # stop starting on boot
journalctl -u adsb-feeder -n 50       # last 50 log lines (for troubleshooting a failed start)
```

Logs go to two places: the app's own rotating file log (`[logging] log_file_path`
in your config) and systemd's journal (`journalctl -u adsb-feeder`). The journal
also captures startup failures that happen before the app's logging is
configured — check it first if the service will not start.
