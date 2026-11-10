#!/usr/bin/env sh
set -eu

image="${1:-text-template-service}"
container="text-template-service-smoke-$$"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker run --detach --name "$container" --publish 18000:8000 "$image" >/dev/null

attempt=0
until curl --fail --silent http://127.0.0.1:18000/healthz >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    docker logs "$container"
    exit 1
  fi
  sleep 1
done

result="$(curl --fail --silent \
  --header 'Content-Type: application/json' \
  --header 'Accept: text/plain' \
  --data '{"source":{"kind":"inline","template":"Hello {{ name }}!"},"context":{"name":"Docker"}}' \
  http://127.0.0.1:18000/v1/render)"

test "$result" = "Hello Docker!"
