"""Tiny web app that returns the client's public originating IP address."""
import os
from ipaddress import ip_address

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix


def _prefers_html() -> bool:
    best = request.accept_mimetypes.best_match(["text/plain", "text/html"])
    return best == "text/html" and request.accept_mimetypes[best] > request.accept_mimetypes["text/plain"]


def create_app(trusted_proxies: int | None = None) -> Flask:
    """Build the app.

    trusted_proxies: number of reverse proxies / load balancers in front of
    the app. When > 0, the client IP is taken from X-Forwarded-For, counting
    that many hops from the right (the entries our own proxies appended).
    Entries further left are client-controlled and ignored, so the header
    can't be spoofed. When 0 (default), the socket peer address is used.
    """
    if trusted_proxies is None:
        trusted_proxies = int(os.environ.get("TRUSTED_PROXIES", "0"))

    app = Flask(__name__)
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

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
