#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:?usage: smoke-test.sh <base-url>}"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# 1. liveness
body=$(curl -fsS "$BASE_URL/health") || fail "/health did not return 200"
[[ $(jq -r .status <<<"$body") == "ok" ]] || fail "/health body: $body"
pass "/health"

# 2. readiness
body=$(curl -fsS "$BASE_URL/ready") || fail "/ready did not return 200"
[[ $(jq -r .status <<<"$body") == "ready" ]] || fail "/ready body: $body"
pass "/ready"

# 3. plain-text IP
ip=$(curl -fsS "$BASE_URL/") || fail "/ did not return 200"
[[ $ip =~ ^[0-9a-fA-F:.]+$ ]] || fail "/ returned '$ip', not an IP"
pass "/ -> $ip"

# 4. JSON
json_ip=$(curl -fsS "$BASE_URL/?format=json" | jq -r .ip)
[[ $json_ip == "$ip" ]] || fail "JSON ip '$json_ip' != text ip '$ip'"
pass "/?format=json"

# 5. HTML
curl -fsS -H "Accept: text/html" "$BASE_URL/" | grep -q 'id="ip"' \
  || fail "HTML page missing the ip element"
pass "HTML"

# 6. spoofed header is ignored (valid while trustedProxies=0)
spoofed=$(curl -fsS -H "X-Forwarded-For: 6.6.6.6" "$BASE_URL/")
[[ $spoofed != "6.6.6.6" ]] || fail "app trusted a spoofed X-Forwarded-For"
pass "X-Forwarded-For spoofing rejected"

echo "All smoke tests passed"
