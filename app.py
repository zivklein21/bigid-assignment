"""Tiny web app that returns the client's public originating IP address."""
import os
from ipaddress import ip_address
from pathlib import Path
from jinja2 import TemplateError

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix


def _prefers_html() -> bool:
    best = request.accept_mimetypes.best_match(["text/plain", "text/html"])
    return best == "text/html" and request.accept_mimetypes[best] > request.accept_mimetypes["text/plain"]

def rediness_checks(app: Flask) -> dict[str, str]:
    """Check what a real request needs. Returns "ok" or "fail: <reason>" per check."""
    checks = {}
    try:
        app.jinja_env.get_template("index.html")
        checks["template"] = "ok"
    except TemplateError as e:
        checks["template"] = f"fail: {e.__class__.__name__}"

    static = Path(app.static_folder or "")
    missing = [f for f in ("style.css", "app.js") if not (static / f).is_file()]
    checks["static"] = f"fail: missing {', '.join(missing)}" if missing else "ok"
    return checks

def create_app(trusted_proxies: int | None = None, template_folder: str = "templates", static_folder: str = "static") -> Flask:
    """Build the app.

    trusted_proxies: number of reverse proxies / load balancers in front of
    the app. When > 0, the client IP is taken from X-Forwarded-For, counting
    that many hops from the right (the entries our own proxies appended).
    Entries further left are client-controlled and ignored, so the header
    can't be spoofed. When 0 (default), the socket peer address is used.
    """
    if trusted_proxies is None:
        trusted_proxies = int(os.environ.get("TRUSTED_PROXIES", "0"))

    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    if trusted_proxies > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_proxies)

    @app.get("/")
    def client_ip():
        ip = request.remote_addr
        fmt = request.args.get("format")
        if fmt == "json":
            return jsonify(ip=ip)
        if fmt == "html" or (fmt is None and _prefers_html()):
            version = ip_address(ip).version if ip else "?"
            return render_template("index.html", ip=ip, version=version)
        return f"{ip}\n", 200, {"Content-Type": "text/plain; charset=utf-8"}

    checks = rediness_checks(app)
    is_ready = all(v == "ok" for v in checks.values())   

    @app.get("/health")
    def health():
        return jsonify(status="ok"), 200, {"Cache-Control": "no-store"}

    @app.get("/ready")
    def ready():
        body = {"status":"ready" if is_ready else "not ready", "checks" : checks}
        return jsonify(body), 200 if is_ready else 503, {"Cache-Control": "no-store"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
