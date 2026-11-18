# bigid-assignment

A tiny Flask web app that returns the client's public originating IP address.

## Endpoints

| Route                | Response                          |
|----------------------|-----------------------------------|
| `GET /`              | Client IP as plain text           |
| `GET /?format=json`  | `{"ip": "<client ip>"}`           |
| `GET /health`        | `{"status": "ok"}`                |

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python app.py                # dev server on :8080
curl localhost:8080/
```

Docker (gunicorn):

```bash
docker build -t whoami-ip .
docker run -p 8080:8080 whoami-ip
```

## Tests

```bash
pytest
```

## Getting the *originating* IP behind proxies

When the app runs behind a load balancer or reverse proxy, the TCP peer is
the proxy, not the client. The real client IP is in `X-Forwarded-For`.
That header can be set by anyone, though, so trusting it blindly lets a
client spoof any IP.

Set `TRUSTED_PROXIES` to the number of proxies in front of the app:

- `0` (default): use the socket peer address and ignore `X-Forwarded-For`.
- `N`: take the client IP from `X-Forwarded-For`, N hops from the right
  (the entries your own proxies appended). Anything further left was
  supplied by the client and is ignored.

Example: behind a single AWS ALB or nginx, run with `TRUSTED_PROXIES=1`.

This uses Werkzeug's `ProxyFix` middleware.
