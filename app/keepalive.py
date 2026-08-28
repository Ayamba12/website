"""Self-ping keep-alive for Render's free tier.

Render spins a free web service down after 15 minutes with no inbound traffic.
A background thread pinging the app's own public URL every 12 minutes counts as
real inbound traffic (it round-trips through Render's edge, not just localhost),
which resets that window before it expires.

Limitation: this only works while the process is already running. If the app
ever does stop (a deploy, a crash, a missed ping), nothing in here can revive
it — only a genuine external request triggers a cold start from a fully
stopped container. This prevents the spin-down from being triggered by
inactivity; it isn't a guarantee the app never goes to sleep.

Only activates when RENDER_EXTERNAL_URL is set (Render sets this automatically
for web services) — a no-op everywhere else, including local dev and tests.
"""
import logging
import os
import threading
import time
import urllib.request

logger = logging.getLogger(__name__)

PING_INTERVAL_SECONDS = 12 * 60  # stay under Render's 15-minute spin-down window


def build_ping_url(external_url: str) -> str:
    return f"{external_url.rstrip('/')}/api/health"


def ping_once(ping_url: str) -> None:
    try:
        with urllib.request.urlopen(ping_url, timeout=10) as resp:
            logger.info("keepalive ping to %s -> %s", ping_url, resp.status)
    except Exception as exc:  # noqa: BLE001 - best-effort, never crash the app over this
        logger.warning("keepalive ping to %s failed: %s", ping_url, exc)


def start_keepalive_pinger():
    external_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not external_url:
        return  # not running on Render as a web service — nothing to do

    ping_url = build_ping_url(external_url)

    def _loop():
        while True:
            time.sleep(PING_INTERVAL_SECONDS)
            ping_once(ping_url)

    thread = threading.Thread(target=_loop, name="keepalive-pinger", daemon=True)
    thread.start()
    logger.info("keepalive pinger started, pinging %s every %ss", ping_url, PING_INTERVAL_SECONDS)
