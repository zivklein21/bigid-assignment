import pytest

from app import create_app


def get(app, path="/", remote="203.0.113.7", xff=None):
    headers = {"X-Forwarded-For": xff} if xff else {}
    return app.test_client().get(
        path, headers=headers, environ_base={"REMOTE_ADDR": remote}
    )


def test_returns_direct_peer_ip_as_text():
    resp = get(create_app(0))
    assert resp.status_code == 200
    assert resp.mimetype == "text/plain"
    assert resp.text == "203.0.113.7\n"


def test_json_format():
    resp = get(create_app(0), "/?format=json")
    assert resp.get_json() == {"ip": "203.0.113.7"}


def test_ignores_forwarded_header_without_trusted_proxy():
    # A client can't spoof its IP when no proxy is trusted.
    resp = get(create_app(0), xff="1.2.3.4")
    assert resp.text == "203.0.113.7\n"


def test_uses_forwarded_header_behind_one_proxy():
    resp = get(create_app(1), remote="10.0.0.5", xff="198.51.100.20")
    assert resp.text == "198.51.100.20\n"


@pytest.mark.parametrize("proxies,expected", [(1, "198.51.100.20"), (2, "192.0.2.1")])
def test_spoofed_entries_are_ignored(proxies, expected):
    # Client injected "6.6.6.6"; trusted proxies appended the real hops on the right.
    resp = get(
        create_app(proxies), remote="10.0.0.5", xff="6.6.6.6, 192.0.2.1, 198.51.100.20"
    )
    assert resp.text == f"{expected}\n"


def test_ipv6():
    resp = get(create_app(0), remote="2001:db8::1")
    assert resp.text == "2001:db8::1\n"


BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


def test_browser_gets_html_page():
    resp = (
        create_app(0)
        .test_client()
        .get(
            "/",
            headers={"Accept": BROWSER_ACCEPT},
            environ_base={"REMOTE_ADDR": "203.0.113.7"},
        )
    )
    assert resp.mimetype == "text/html"
    assert "203.0.113.7" in resp.text
    assert "IPv4" in resp.text


def test_curl_default_accept_gets_plain_text():
    resp = (
        create_app(0)
        .test_client()
        .get(
            "/", headers={"Accept": "*/*"}, environ_base={"REMOTE_ADDR": "203.0.113.7"}
        )
    )
    assert resp.text == "203.0.113.7\n"


def test_html_format_param():
    resp = get(create_app(0), "/?format=html", remote="2001:db8::1")
    assert resp.mimetype == "text/html"
    assert "IPv6" in resp.text


def test_static_assets_served():
    client = create_app(0).test_client()
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_health():
    assert get(create_app(0), "/health").get_json() == {"status": "ok"}

def test_ready_ok():
    resp = get(create_app(0), "/ready")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "status": "ready",
        "checks": {"templates": "ok", "static": "ok"},
    }

def test_ready_fails_when_templates_missing(tmp_path):
    resp = get(create_app(0, template_folder=str(tmp_path)), "/ready")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "not ready"
    assert body["checks"]["templates"].startswith("fail")
    assert body["checks"]["static"] == "ok"

def test_ready_fails_when_static_missing(tmp_path):
    resp = get(create_app(0, static_folder=str(tmp_path)), "/ready")
    assert resp.status_code == 503
    assert resp.get_json()["checks"]["static"] == "fail: missing style.css, app.js"

@pytest.mark.parametrize("path", ["/health", "/ready"])
def test_probes_not_cached(path):
    assert get(create_app(0), path).headers["cache-control"] == "no-store"