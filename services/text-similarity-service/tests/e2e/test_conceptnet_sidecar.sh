#!/usr/bin/env bash
# End-to-end test: main text-similarity-service <-> conceptnet-sidecar.
#
# Exercises:
#   1. Happy path — conceptnet_numberbatch / backend=local returns a valid score,
#      both on a cold call (sidecar lazy-loads the model) and a warm call.
#   2. Sidecar down — with the sidecar stopped, the main service returns 503 but
#      stays healthy (/health = 200).
#   3. Idle eviction — with a short TTL the model is evicted (/v1/status shows
#      model_loaded:false) yet a follow-up request still succeeds (auto reload).
#   4. Backward compat — the response envelope shape is unchanged.
#
# Prereqs: docker compose, a mounted Numberbatch model at ./model/.
# Usage:    tests/e2e/test_conceptnet_sidecar.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_URL="http://localhost:18000"
SIDECAR_URL="http://localhost:18200"
COMPOSE="$ROOT/docker-compose.test.yml"

main_ready() {
  curl -sf "$MAIN_URL/health" | grep -q '"status":"ok"'
}

# ── Start the stack ──────────────────────────────────────────────────────────
echo "==> Starting test stack"
docker compose -f "$COMPOSE" up --build -d

trap 'docker compose -f "$COMPOSE" down -v' EXIT

echo -n "==> Waiting for main service health"
for _ in $(seq 1 60); do
  if main_ready; then break; fi
  echo -n "."
  sleep 2
done
echo
main_ready || { echo "main service never became healthy" >&2; exit 1; }

# ── 1. Happy path ────────────────────────────────────────────────────────────
echo "==> (1) Happy path — cold call (sidecar lazy-loads the model)"
COLD=$(curl -sf -X POST "$MAIN_URL/v1/similarity/text/distance" \
  -H 'Content-Type: application/json' \
  -d '{"algorithm":"embedding_cosine","params":{"variant":"conceptnet_numberbatch","backend":"local"},"inputs":[{"id":"p1","a":"king","b":"queen"}]}')
echo "$COLD" | python3 -c "import sys,json; d=json.load(sys.stdin); r=d['results'][0]['result']; assert 'similarity' in r, r; assert 'raw' in r and 'distance' in r, r; print('cold OK:', r['similarity'])"

echo "==> (1) Happy path — warm call (model still loaded)"
WARM=$(curl -sf -X POST "$MAIN_URL/v1/similarity/text/distance" \
  -H 'Content-Type: application/json' \
  -d '{"algorithm":"embedding_cosine","params":{"variant":"conceptnet_numberbatch","backend":"local"},"inputs":[{"id":"p1","a":"king","b":"queen"}]}')
echo "$WARM" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'similarity' in d['results'][0]['result']; print('warm OK')"

# ── 2. Sidecar down → 503, main stays healthy ────────────────────────────────
echo "==> (2) Sidecar down → clean 503, main stays healthy"
docker compose -f "$COMPOSE" stop conceptnet-sidecar >/dev/null
for _ in $(seq 1 30); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$MAIN_URL/v1/similarity/text/distance" \
    -H 'Content-Type: application/json' \
    -d '{"algorithm":"embedding_cosine","params":{"variant":"conceptnet_numberbatch"},"inputs":[{"id":"p1","a":"king","b":"queen"}]}')
  [ "$CODE" = "503" ] && break
  sleep 1
done
[ "$CODE" = "503" ] || { echo "expected 503, got $CODE" >&2; exit 1; }
curl -sf "$MAIN_URL/health" | grep -q '"status":"ok"' && echo "sidecar-down OK (503 + healthy)"

docker compose -f "$COMPOSE" start conceptnet-sidecar >/dev/null
for _ in $(seq 1 30); do
  curl -sf "$SIDECAR_URL/health/ready" >/dev/null 2>&1 && break
  sleep 1
done

# ── 3. Idle eviction visible across the process boundary ─────────────────────
echo "==> (3) Idle eviction (TTL=1s) then auto-reload"
# Tickle the sidecar so a model is resident, then let the TTL elapse.
curl -sf -X POST "$SIDECAR_URL/v1/relatedness" -H 'Content-Type: application/json' \
  -d '{"pairs":[{"id":"p1","word_a":"king","word_b":"queen","lang":"en"}]}' >/dev/null
sleep 3
STATUS=$(curl -sf "$SIDECAR_URL/v1/status")
echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['model_loaded'] is False, d; print('evicted OK')"
# Follow-up through the main service reloads it automatically.
RELOAD=$(curl -sf -X POST "$MAIN_URL/v1/similarity/text/distance" \
  -H 'Content-Type: application/json' \
  -d '{"algorithm":"embedding_cosine","params":{"variant":"conceptnet_numberbatch"},"inputs":[{"id":"p1","a":"king","b":"queen"}]}')
echo "$RELOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'similarity' in d['results'][0]['result']; print('auto-reload OK')"

echo "==> All end-to-end ConceptNet sidecar tests passed"
