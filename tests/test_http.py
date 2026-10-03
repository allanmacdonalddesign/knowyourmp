import httpx
import pytest
import respx

from civic import http
from civic.cache import HttpCache, connect


@pytest.fixture
def fetcher(tmp_path, monkeypatch):
    monkeypatch.setenv("CIVIC_DB", str(tmp_path / "c.db"))
    f = http.Fetcher(HttpCache(connect(tmp_path / "c.db")), min_interval=0)
    f.waits = []
    f.sleep = lambda s: f.waits.append(s)
    return f


@respx.mock
def test_retries_server_errors_then_succeeds(fetcher):
    route = respx.get("https://x.test/a").mock(side_effect=[httpx.Response(502), httpx.Response(503), httpx.Response(200, json={"ok": 1})])
    assert fetcher.get_json("https://x.test/a") == {"ok": 1}
    assert route.call_count == 3 and fetcher.waits == [3, 10]


@respx.mock
def test_gives_up_after_the_last_retry(fetcher):
    respx.get("https://x.test/a").mock(return_value=httpx.Response(502))
    with pytest.raises(httpx.HTTPStatusError):
        fetcher.get_text("https://x.test/a")
    assert fetcher.waits == list(http.RETRY_WAITS)


@respx.mock
def test_client_errors_are_not_retried(fetcher):
    route = respx.get("https://x.test/a").mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        fetcher.get_text("https://x.test/a")
    assert route.call_count == 1 and fetcher.waits == []


@respx.mock
def test_network_errors_are_retried(fetcher):
    respx.get("https://x.test/a").mock(side_effect=[httpx.ConnectError("boom"), httpx.Response(200, text="hi")])
    assert fetcher.get_text("https://x.test/a") == "hi"
