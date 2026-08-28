import threading
from unittest.mock import patch

from app.keepalive import build_ping_url, ping_once, start_keepalive_pinger


def test_build_ping_url_strips_trailing_slash():
    assert build_ping_url("https://myapp.onrender.com/") == "https://myapp.onrender.com/api/health"
    assert build_ping_url("https://myapp.onrender.com") == "https://myapp.onrender.com/api/health"


def test_ping_once_swallows_errors():
    with patch("app.keepalive.urllib.request.urlopen", side_effect=OSError("network down")):
        ping_once("https://myapp.onrender.com/api/health")  # must not raise


def test_start_keepalive_pinger_noop_without_render_url(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    before = threading.active_count()
    start_keepalive_pinger()
    assert threading.active_count() == before


def test_start_keepalive_pinger_starts_thread_on_render(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://myapp.onrender.com")
    before = {t.name for t in threading.enumerate()}
    start_keepalive_pinger()
    after = {t.name for t in threading.enumerate()}
    assert "keepalive-pinger" in (after - before)
