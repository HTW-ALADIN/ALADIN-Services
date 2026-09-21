#!/bin/sh
set -eu

image_name="${1:-natural-language-generation-service}"
container_id="$(docker run --detach --rm --publish 127.0.0.1::8000 "$image_name")"

cleanup() {
  docker rm --force "$container_id" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

host_port="$(docker port "$container_id" 8000/tcp | sed 's/.*://')"
base_url="http://127.0.0.1:${host_port}"

attempt=0
until curl --fail --silent "${base_url}/healthz" >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    docker logs "$container_id"
    exit 1
  fi
  sleep 1
done

response="$(curl --fail --silent \
  --request POST \
  --header 'Content-Type: application/json' \
  --header 'Accept: text/plain' \
  --data-binary @examples/english-constituent.json \
  "${base_url}/v1/generate")"

test "$response" = "The cat chases the mouse."

template_response="$(curl --fail --silent \
  --request POST \
  --header 'Content-Type: application/json' \
  --header 'Accept: text/plain' \
  --data-binary @examples/english-template.json \
  "${base_url}/v1/generate")"

test "$template_response" = "<p>Hi Alice. They are ready.</p>"

cli_response="$(docker run --rm --interactive "$image_name" \
  node dist/src/cli/index.js generate --request - \
  < examples/english-constituent.json)"
test "$cli_response" = "The cat chases the mouse."

template_cli_response="$(docker run --rm --interactive "$image_name" \
  node dist/src/cli/index.js generate --request - \
  < examples/english-template.json)"
test "$template_cli_response" = "<p>Hi Alice. They are ready.</p>"

printf '%s\n' 'Docker REST and CLI smoke tests passed.'
