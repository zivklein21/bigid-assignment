# bigid-assignment

[![CI](https://github.com/zivklein21/bigid-assignment/actions/workflows/ci.yml/badge.svg)](https://github.com/zivklein21/bigid-assignment/actions/workflows/ci.yml)

A tiny Flask web app that returns the client's public originating IP address,
correctly and spoof-safely, even when running behind load balancers and reverse proxies.

## Endpoints

| Route     | Purpose                                   | Status codes |
|-----------|-------------------------------------------|--------------|
| `/`       | Client IP (text / JSON / HTML)            | 200          |
| `/health` | Liveness probe: is the process alive?     | 200          |
| `/ready`  | Readiness probe: can it serve traffic?    | 200 / 503    |

### `/`: client IP

The response format depends on the request:

```bash
# Plain text (default for curl and scripts)
$ curl localhost:8080/
203.0.113.7

# JSON
$ curl "localhost:8080/?format=json"
{"ip":"203.0.113.7"}

# HTML (browsers get this automatically via the Accept header)
$ curl -H "Accept: text/html" localhost:8080/
<!doctype html> ... <code id="ip">203.0.113.7</code> ...
```

`?format=html` forces the HTML page.

### `/health`: liveness

Deliberately has no dependencies. If it fails, the orchestrator restarts the container.

```bash
$ curl localhost:8080/health
{"status":"ok"}
```

### `/ready`: readiness

Checks what a real request needs: the template loads and the static assets
exist. These are checked once at startup, since files in the image don't change
at runtime. If anything fails it returns **503**, and the orchestrator stops sending
traffic to the container without restarting it.

```bash
$ curl -i localhost:8080/ready
HTTP/1.1 200 OK
{"status":"ready","checks":{"templates":"ok","static":"ok"}}
```

Both probes send `Cache-Control: no-store`, so no proxy caches a probe result.

## Repository structure

```
.
├── app.py                 # Flask app: routes, proxy handling, readiness checks
├── templates/index.html   # HTML page
├── static/                # CSS + JS (copy button)
├── tests/test_app.py      # pytest suite
├── charts/                # Helm chart for Kubernetes deployment
├── .github/workflows/     # CI: tests → build image
├── Dockerfile             # Production image (gunicorn, non-root)
├── pyproject.toml         # Dependencies: prod + dev group (uv)
└── uv.lock                # Locked versions
```

## Running locally

### 1. Without Docker

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                    # creates .venv with prod + dev dependencies
uv run pytest              # run the tests
uv run python app.py       # dev server on http://localhost:8080
```

### 2. With Docker

```bash
docker build -t bigid-assignment .
docker run --rm -p 8080:8080 bigid-assignment
curl localhost:8080/
```

### 3. On Kubernetes (kind + Helm)

```bash
kind create cluster
kind load docker-image bigid-assignment
helm install whoami ./charts/bigid-assignment
kubectl port-forward svc/whoami-bigid-assignment 8080:80
curl localhost:8080/
```

## Configuration

| Variable          | Default | Description                                     |
|-------------------|---------|-------------------------------------------------|
| `PORT`            | `8080`  | Port to listen on                               |
| `TRUSTED_PROXIES` | `0`     | Number of reverse proxies in front of the app   |

## Design decision: identifying the client IP

**The problem.** Behind a load balancer or reverse proxy, the TCP connection
comes from the proxy, so `remote_addr` is the proxy's IP, not the client's.
Proxies pass the original address in the `X-Forwarded-For` header, and each hop
appends the address it received the connection from:

```
X-Forwarded-For: <client>, <proxy1>, <proxy2>
```

**Why it can be spoofed.** It's an ordinary request header, and the client can
send it with any value it likes. The proxies don't replace it; they *append* to it:

```bash
curl -H "X-Forwarded-For: 6.6.6.6" https://the-app/
# The app receives:  X-Forwarded-For: 6.6.6.6, <real client IP>
```

An app that takes the **leftmost** entry, which is the common naive approach,
returns `6.6.6.6`, the value the attacker chose. That breaks anything built on
the IP: rate limiting, allow-lists, audit logs.

**The fix: `TRUSTED_PROXIES`.** The only trustworthy entries are the ones added
by *our own* proxies, and they are always at the **right** end of the list.
So the app counts from the right:

- `TRUSTED_PROXIES=0` (default): ignore the header entirely and use the socket
  address. This is safe when the app is exposed directly.
- `TRUSTED_PROXIES=N`: take the client IP from the Nth entry from the right.
  Everything to the left of it is client-controlled and ignored.

```
X-Forwarded-For: 6.6.6.6, 198.51.100.20        (via 1 proxy, e.g. an ingress)
                 ^ spoofed  ^ added by our proxy → TRUSTED_PROXIES=1 returns this
```

The value has to match the real deployment topology. If it's too low, you get
the proxy's IP. If it's too high, you trust a client-supplied value again. For
example, a single ingress-nginx or AWS ALB means `TRUSTED_PROXIES=1`.

The implementation uses Werkzeug's `ProxyFix(x_for=N)` rather than custom parsing.
The tests cover the spoofing case directly (`test_spoofed_entries_are_ignored`).
