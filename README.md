# bigid-assignment

[![CI](https://github.com/zivklein21/bigid-assignment/actions/workflows/ci.yaml/badge.svg)](https://github.com/zivklein21/bigid-assignment/actions/workflows/ci.yaml)

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
├── Dockerfile             # Multi-stage build: uv + PyInstaller → single binary
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

The Dockerfile is a multi-stage build. The `builder` stage uses uv to install the
dependencies, then PyInstaller bundles `app.py`, `templates/` and `static/` into
one executable. The `runtime` stage contains only that executable.

**Build the image**

```bash
docker build -t bigid-assignment .
```

**Run in the foreground** (Ctrl+C stops it; `--rm` removes the container afterwards)

```bash
docker run --rm -p 8080:8080 bigid-assignment
```

**Run in the background (detached)**

```bash
docker run -d --name bigid -p 8080:8080 bigid-assignment

docker ps --filter name=bigid    # STATUS should say "Up"
docker logs -f bigid             # follow the app logs
```

**Check that it works**

```bash
curl localhost:8080/                 # your IP as plain text
curl "localhost:8080/?format=json"   # {"ip":"..."}
curl localhost:8080/health           # {"status":"ok"}
curl -i localhost:8080/ready         # 200 when the templates and static files are present
```

**Configuration.** Pass settings as environment variables (see
[Configuration](#configuration)). If you change `PORT`, change the container
side of `-p` to match:

```bash
docker run -d --name bigid -p 9000:9000 -e PORT=9000 -e TRUSTED_PROXIES=1 bigid-assignment
```

**Stop and clean up**

```bash
docker stop bigid && docker rm bigid
```

If a detached container exits immediately, run `docker logs bigid` to see why.
Also make sure you ran the `bigid-assignment` tag and not another image ID.

### 3. On Kubernetes (kind + Helm)

```bash
kind create cluster
docker build -t bigid-assignment .
kind load docker-image bigid-assignment

# Use the locally built image instead of the GHCR default
helm install whoami ./charts/bigid-assignment \
  --set image.repository=bigid-assignment,image.tag=latest,image.pullPolicy=Never

kubectl get pods -l app.kubernetes.io/instance=whoami   # wait for 1/1 Ready
kubectl port-forward svc/whoami-bigid-assignment 8080:80
curl localhost:8080/
```

See [Deploying with Helm](#deploying-with-helm) for configuration and secrets.

## Published image

CI builds the image on every pull request and on every push to `main`.
Only pushes to `main` publish it, to GitHub Container Registry:

```
ghcr.io/zivklein21/bigid-assignment:<commit-sha>
```

The tag is the first 10 characters of the commit SHA that was built, so every image
maps to exactly one commit. There is no `latest` tag: deploy a specific SHA.

```bash
# Find the SHA of a commit on main
git log -1 --format=%H | cut -c1-10

# Pull and run that image
docker pull ghcr.io/zivklein21/bigid-assignment:<commit-sha>
docker run --rm -p 8080:8080 ghcr.io/zivklein21/bigid-assignment:<commit-sha>
```

All published tags are listed on the repository's
[Packages page](https://github.com/zivklein21/bigid-assignment/pkgs/container/bigid-assignment).

## Configuration

| Variable          | Default | Description                                     |
|-------------------|---------|-------------------------------------------------|
| `PORT`            | `8080`  | Port to listen on                               |
| `TRUSTED_PROXIES` | `0`     | Number of reverse proxies in front of the app   |

## Deploying with Helm

The chart lives in [`charts/bigid-assignment`](charts/bigid-assignment) and passes
`helm lint --strict`.

```bash
# Deploy a published image (always pin a commit SHA; there is no `latest`)
helm install whoami ./charts/bigid-assignment --set image.tag=<commit-sha>

# Upgrade with your own overrides
helm upgrade whoami ./charts/bigid-assignment -f my-values.yaml
```

### Main values

| Key                                   | Default                               | Description                                                   |
|---------------------------------------|---------------------------------------|---------------------------------------------------------------|
| `image.repository`                    | `ghcr.io/zivklein21/bigid-assignment` | Image to run                                                  |
| `image.tag`                           | `""` (→ `appVersion`)                 | Commit SHA to deploy                                          |
| `replicaCount`                        | `2`                                   | Ignored when `autoscaling.enabled=true`                       |
| `config.trustedProxies`               | `0`                                   | → `TRUSTED_PROXIES`. Use `1` behind ingress-nginx / an ALB    |
| `resources`                           | req `50m`/`64Mi`, lim `200m`/`128Mi`  | Container requests and limits                                 |
| `livenessProbe`                       | `GET /health` every 10s               | Restart the container if it hangs                             |
| `readinessProbe`                      | `GET /ready` every 5s                 | Remove the pod from the Service while it returns 503          |
| `startupProbe.enabled`                | `true`                                | `GET /health`, up to ~60s (30 × 2s) to start                  |
| `existingSecret`                      | `""`                                  | Secret whose keys become env vars (see [Secrets](#secrets))   |
| `env` / `envFrom`                     | `[]`                                  | Extra env vars / sources                                      |
| `ingress.enabled`                     | `false`                               | Create an Ingress                                             |
| `autoscaling.enabled`                 | `false`                               | Create an HPA (2–5 replicas, 80% CPU)                         |
| `podDisruptionBudget.enabled`         | `false`                               | Create a PDB (`minAvailable: 1`)                              |

### Probes

- **Liveness:** `/health`. It has no dependencies, so it fails only if the process is stuck.
- **Readiness:** `/ready`. It returns 503 when the templates or static files are missing.
- **Startup:** `/health`. The PyInstaller binary unpacks itself into `/tmp` on boot, so the
  startup probe holds off liveness checks until the app is up. Set
  `startupProbe.enabled=false` to turn it off.

Every probe field can be overridden. Anything you set replaces the default:

```yaml
# my-values.yaml
readinessProbe:
  httpGet: { path: /ready, port: http }
  periodSeconds: 10
  failureThreshold: 6
startupProbe:
  enabled: true
  httpGet: { path: /health, port: http }
  periodSeconds: 5
  failureThreshold: 24
```

### Security defaults

The pod runs as non-root UID `10001` with a read-only root filesystem (an `emptyDir` is
mounted at `/tmp` for the PyInstaller unpack). All Linux capabilities are dropped,
privilege escalation is disabled, and the `RuntimeDefault` seccomp profile is used. The
ServiceAccount token is not mounted, since the app doesn't call the Kubernetes API.

### Secrets

The app needs no secrets today. This section describes the supported way to add them.

**The rule:** the chart never creates a Secret, and `values.yaml` has no field for secret
values. Anything passed through values ends up in git, in shell history (`--set`) and in
the Helm release object (`sh.helm.release.v1.*`), which anyone who can read Secrets in the
namespace can decode. Secrets are created **outside** the chart and referenced **by name**.

**Using a Secret in the chart.** There are two ways:

```yaml
# 1. Load every key of the Secret as an env var (envFrom.secretRef)
existingSecret: whoami-secrets

# 2. Pick individual keys
env:
  - name: API_KEY
    valueFrom:
      secretKeyRef:
        name: whoami-secrets
        key: api-key
```

**Creating the Secret.** Pick the method that matches the environment:

1. **Plain Kubernetes Secret (local / dev).** Create it imperatively and never commit it:

   ```bash
   kubectl create secret generic whoami-secrets \
     --from-literal=API_KEY=changeme
   # or from a local, git-ignored file
   kubectl create secret generic whoami-secrets --from-env-file=.env
   ```

2. **Sealed Secrets (GitOps).** Encrypt the Secret with the cluster's public key. The
   resulting `SealedSecret` is safe to commit, and the
   [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets) controller decrypts it
   in-cluster into `whoami-secrets`:

   ```bash
   kubectl create secret generic whoami-secrets \
     --from-literal=API_KEY=changeme --dry-run=client -o yaml \
     | kubeseal -o yaml > sealed-secret.yaml
   kubectl apply -f sealed-secret.yaml
   ```

3. **External Secrets Operator (cloud secret manager).** The secret stays in Vault, AWS
   Secrets Manager, GCP Secret Manager or similar. The
   [External Secrets Operator](https://external-secrets.io) syncs it into `whoami-secrets`
   and keeps it up to date when it rotates:

   ```yaml
   apiVersion: external-secrets.io/v1
   kind: ExternalSecret
   metadata:
     name: whoami-secrets
   spec:
     refreshInterval: 1h
     secretStoreRef:
       kind: ClusterSecretStore
       name: aws-secrets-manager      # defined once by the platform team
     target:
       name: whoami-secrets           # the Secret the chart references
     data:
       - secretKey: API_KEY
         remoteRef:
           key: prod/whoami
           property: api-key
   ```

In all three cases the chart side is the same: `existingSecret: whoami-secrets`.

Non-secret settings (`TRUSTED_PROXIES`, `PORT`) are plain configuration. Set them through
`config.*` or `env`, not a Secret.

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
