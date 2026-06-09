#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# smoke-test.sh — End-to-end smoke tests for graph-rewriting-service
#
# Usage:
#   ./scripts/smoke-test.sh [BASE_URL]
#
# Environment variables:
#   BASE_URL          Service base URL  (default: http://localhost:8080)
#
# This script tests two scenarios:
#   1. In-memory backend (DB_BACKEND=memory) — no Neo4j required
#   2. Neo4j backend (DB_BACKEND=neo4j) — requires Neo4j via docker-compose
#
# Exit code: 0 = all tests passed, 1 = one or more failures
# ---------------------------------------------------------------------------
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-http://127.0.0.1:8080}}"

PASS=0
FAIL=0

# ---- helpers ---------------------------------------------------------------

green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }

assert() {
    local label="$1"
    local expected_status="$2"
    local actual_status="$3"
    local body="$4"

    if [[ "$actual_status" == "$expected_status" ]]; then
        green "  PASS  [$actual_status] $label"
        (( PASS++ )) || true
    else
        red   "  FAIL  [$actual_status != $expected_status] $label"
        red   "         body: $body"
        (( FAIL++ )) || true
    fi
}

# Usage: get LABEL EXPECTED_STATUS URL
get() {
    local label="$1" expected="$2" url="$3"
    local response
    response=$(curl -s -w '\n%{http_code}' "$url")
    local http_body http_status
    http_body=$(echo "$response" | head -n -1)
    http_status=$(echo "$response" | tail -n 1)
    assert "$label" "$expected" "$http_status" "$http_body"
}

# Usage: post LABEL EXPECTED_STATUS URL JSON_BODY
post() {
    local label="$1" expected="$2" url="$3" body="$4"
    local response
    response=$(curl -s -w '\n%{http_code}' -X POST "$url" \
        -H 'Content-Type: application/json' \
        -d "$body")
    local http_body http_status
    http_body=$(echo "$response" | head -n -1)
    http_status=$(echo "$response" | tail -n 1)
    assert "$label" "$expected" "$http_status" "$http_body"
}

# Usage: post_body_contains LABEL EXPECTED_STATUS URL JSON_BODY NEEDLE
post_body_contains() {
    local label="$1" expected="$2" url="$3" body="$4" needle="$5"
    local response
    response=$(curl -s -w '\n%{http_code}' -X POST "$url" \
        -H 'Content-Type: application/json' \
        -d "$body")
    local http_body http_status
    http_body=$(echo "$response" | head -n -1)
    http_status=$(echo "$response" | tail -n 1)
    assert "$label (HTTP $expected)" "$expected" "$http_status" "$http_body"
    if [[ "$http_status" == "$expected" ]]; then
        if echo "$http_body" | grep -q "$needle"; then
            green "  PASS  body contains \"$needle\""
            (( PASS++ )) || true
        else
            red   "  FAIL  body does not contain \"$needle\""
            red   "         body: $http_body"
            (( FAIL++ )) || true
        fi
    fi
}

wait_for_service() {
    local url="$1"
    echo -n "  Waiting for service at ${url}..."
    for _ in $(seq 1 15); do
        if curl -sf "${url}/health" >/dev/null 2>&1; then
            echo " OK"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    echo " TIMEOUT"
    return 1
}

# ---- shared test payloads --------------------------------------------------

TRANSFORM_PAYLOAD='{
    "hostgraph": {
        "options": { "type": "directed" },
        "nodes": [
            { "key": "A", "attributes": { "label": "A", "type": "Event" } },
            { "key": "B", "attributes": { "label": "B", "type": "Function" } }
        ],
        "edges": [
            { "key": "aToB", "source": "A", "target": "B", "attributes": {} }
        ]
    },
    "rules": [
        {
            "key": "add_node",
            "patternGraph": {
                "options": { "type": "directed" },
                "nodes": [
                    { "key": "A", "attributes": { "label": "A" } }
                ],
                "edges": []
            },
            "replacementGraph": {
                "options": { "type": "directed" },
                "nodes": [
                    { "key": "A", "attributes": { "label": "A" } },
                    { "key": "C", "attributes": { "label": "C", "type": "NewNode" } }
                ],
                "edges": [
                    { "key": "aToC", "source": "A", "target": "C", "attributes": {} }
                ]
            }
        }
    ]
}'

FIND_PAYLOAD='{
    "hostgraph": {
        "options": { "type": "directed" },
        "nodes": [
            { "key": "A", "attributes": { "label": "A", "type": "Event" } },
            { "key": "B", "attributes": { "label": "B", "type": "Function" } }
        ],
        "edges": [
            { "key": "aToB", "source": "A", "target": "B", "attributes": {} }
        ]
    },
    "rules": [
        {
            "key": "find_node",
            "patternGraph": {
                "options": { "type": "directed" },
                "nodes": [
                    { "key": "A", "attributes": {} }
                ],
                "edges": []
            }
        }
    ]
}'

HOSTGRAPH_PAYLOAD='{
    "hostgraph": {
        "options": { "type": "directed" },
        "nodes": [
            { "key": "X", "attributes": { "label": "X" } },
            { "key": "Y", "attributes": { "label": "Y" } }
        ],
        "edges": [
            { "key": "xToY", "source": "X", "target": "Y", "attributes": {} }
        ]
    },
    "rules": []
}'

NODE_PAYLOAD='{ "key": "smokeNode1", "attributes": { "label": "SmokeTest" } }'
EDGE_PAYLOAD='{ "key": "smokeEdge1", "source": "smokeNode1", "target": "smokeNode2", "attributes": { "type": "test" } }'

# ---- core API tests (run for both backends) --------------------------------

run_api_tests() {
    local backend="$1"
    echo ""
    echo "── API tests (backend: ${backend}) ─────────────────────────────────"

    # 1. Health check
    get "health" "200" "${BASE_URL}/health"

    # 2. Create node
    post "create node" "201" "${BASE_URL}/node" "$NODE_PAYLOAD"

    # 3. Get node
    get "get node" "200" "${BASE_URL}/node/smokeNode1"

    # 4. Create second node for edge
    post "create node 2" "201" "${BASE_URL}/node" \
        '{ "key": "smokeNode2", "attributes": { "label": "SmokeTest2" } }'

    # 5. Create edge
    post "create edge" "201" "${BASE_URL}/edge" "$EDGE_PAYLOAD"

    # 6. Get edge
    get "get edge" "200" "${BASE_URL}/edge/smokeEdge1"

    # 7. Get all nodes
    get "get all nodes" "200" "${BASE_URL}/nodes"

    # 8. Delete edge
    local del_response
    del_response=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "${BASE_URL}/edge/smokeEdge1")
    assert "delete edge" "204" "$del_response" ""

    # 9. Delete node
    del_response=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "${BASE_URL}/node/smokeNode1")
    assert "delete node" "204" "$del_response" ""

    # 10. Delete all nodes
    del_response=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "${BASE_URL}/nodes")
    assert "delete all nodes" "204" "$del_response" ""

    # 11. Import hostgraph via /hostgraph
    post_body_contains "import hostgraph" "200" "${BASE_URL}/hostgraph" \
        "$HOSTGRAPH_PAYLOAD" "success"

    # 12. Transform
    post_body_contains "transform graph" "200" "${BASE_URL}/transform" \
        "$TRANSFORM_PAYLOAD" "NewNode"

    # 13. Find pattern
    post_body_contains "find pattern" "200" "${BASE_URL}/find" \
        "$FIND_PAYLOAD" "data"

    # 14. Get node not found
    get "get missing node (404)" "404" "${BASE_URL}/node/nonexistent_node_xyz"

    # 15. Invalid transform payload
    post "invalid transform (400)" "400" "${BASE_URL}/transform" \
        '{"invalid": "payload"}'
}

# ---- memory backend tests --------------------------------------------------

memory_tests() {
    echo ""
    echo "══════════════════════════════════════════════════════════════════════"
    echo "  Testing IN-MEMORY backend (container)"
    echo "══════════════════════════════════════════════════════════════════════"

    local CONTAINER_NAME="grs-smoke-memory"
    local IMAGE_NAME="graph-rewriting-service:smoke-test"

    # Build Docker image (includes its own npm run build via builder stage)
    echo "  Building Docker image..."
    if ! docker build -t "$IMAGE_NAME" . >/dev/null 2>&1; then
        red "  FAIL  Docker image build failed"
        (( FAIL++ )) || true
        return
    fi
    echo "  Docker image built."

    # Remove any leftover container from a previous interrupted run
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

    # Free port 8080 if something else is already bound to it
    local occupant
    occupant=$(docker ps -q --filter "publish=8080" 2>/dev/null)
    if [[ -n "$occupant" ]]; then
        echo "  Removing container occupying port 8080 ($occupant)..."
        docker rm -f "$occupant" >/dev/null 2>&1 || true
        sleep 1
    fi

    # Start container with memory backend (default, but explicit for clarity)
    docker run -d --name "$CONTAINER_NAME" \
        -p 8080:8080 \
        -e DB_BACKEND=memory \
        "$IMAGE_NAME" >/dev/null

    trap "docker rm -f $CONTAINER_NAME >/dev/null 2>&1 || true" RETURN

    if ! wait_for_service "$BASE_URL"; then
        red "  FAIL  Container did not start (memory backend)"
        (( FAIL++ )) || true
        docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
        return
    fi

    run_api_tests "memory (container)"

    # Memory-specific health check
    get "memory health" "200" "${BASE_URL}/memory/health"

    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    sleep 1
}

# ---- neo4j backend tests ---------------------------------------------------

neo4j_tests() {
    if [[ -z "${NEO4J_URI:-}" ]]; then
        echo ""
        echo "══════════════════════════════════════════════════════════════════════"
        echo "  Neo4j backend — SKIPPED (NEO4J_URI not set)"
        echo "  Set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD to run these tests."
        echo "══════════════════════════════════════════════════════════════════════"
        return
    fi

    echo ""
    echo "══════════════════════════════════════════════════════════════════════"
    echo "  Testing NEO4J backend (${NEO4J_URI})"
    echo "══════════════════════════════════════════════════════════════════════"

    DB_BACKEND=neo4j APP_ENV=production node dist/index.js &
    local SERVER_PID=$!
    trap "kill $SERVER_PID 2>/dev/null || true" RETURN

    if ! wait_for_service "$BASE_URL"; then
        red "  FAIL  Server did not start (neo4j backend)"
        (( FAIL++ )) || true
        kill "$SERVER_PID" 2>/dev/null || true
        return
    fi

    run_api_tests "neo4j"

    # Neo4j-specific health check
    get "neo4j health" "200" "${BASE_URL}/neo4j/health"

    kill "$SERVER_PID" 2>/dev/null || true
    sleep 1
}

# ---- CLI tests (Neo4j only) ------------------------------------------------

cli_tests() {
    if [[ -z "${NEO4J_URI:-}" ]]; then
        echo ""
        echo "══════════════════════════════════════════════════════════════════════"
        echo "  CLI tests — SKIPPED (NEO4J_URI not set)"
        echo "  Set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD to run these tests."
        echo "══════════════════════════════════════════════════════════════════════"
        return
    fi

    echo ""
    echo "══════════════════════════════════════════════════════════════════════"
    echo "  Testing CLI (Neo4j backend: ${NEO4J_URI})"
    echo "══════════════════════════════════════════════════════════════════════"

    local cli="node dist/cli.js"
    local tmpdir
    tmpdir=$(mktemp -d)

    # helper: run CLI command, check exit code and optionally a string in output
    cli_ok() {
        local label="$1" needle="$2"
        shift 2
        local output
        if output=$($cli "$@" 2>&1); then
            if [[ -n "$needle" ]] && ! echo "$output" | grep -q "$needle"; then
                red "  FAIL  $label — missing \"$needle\" in output"
                red "         output: $output"
                (( FAIL++ )) || true
            else
                green "  PASS  $label"
                (( PASS++ )) || true
            fi
        else
            red "  FAIL  $label — command exited with error"
            red "         output: $output"
            (( FAIL++ )) || true
        fi
    }

    # Write fixture files
    cat > "$tmpdir/node1.json" <<'EOF'
{ "key": "cliNode1", "attributes": { "label": "CLI-Test" } }
EOF
    cat > "$tmpdir/node2.json" <<'EOF'
{ "key": "cliNode2", "attributes": { "label": "CLI-Test2" } }
EOF
    cat > "$tmpdir/edge.json" <<'EOF'
{ "key": "cliEdge1", "source": "cliNode1", "target": "cliNode2", "attributes": { "type": "cli-test" } }
EOF
    cat > "$tmpdir/transform.json" <<'EOF'
{
  "hostgraph": {
    "options": { "type": "directed" },
    "nodes": [
      { "key": "A", "attributes": { "label": "A", "type": "Event" } },
      { "key": "B", "attributes": { "label": "B", "type": "Function" } }
    ],
    "edges": [{ "key": "aToB", "source": "A", "target": "B", "attributes": {} }]
  },
  "rules": [{
    "key": "add_node",
    "patternGraph": {
      "options": { "type": "directed" },
      "nodes": [{ "key": "A", "attributes": { "label": "A" } }],
      "edges": []
    },
    "replacementGraph": {
      "options": { "type": "directed" },
      "nodes": [
        { "key": "A", "attributes": { "label": "A" } },
        { "key": "C", "attributes": { "label": "C", "type": "NewNode" } }
      ],
      "edges": [{ "key": "aToC", "source": "A", "target": "C", "attributes": {} }]
    }
  }]
}
EOF
    cat > "$tmpdir/find.json" <<'EOF'
{
  "hostgraph": {
    "options": { "type": "directed" },
    "nodes": [
      { "key": "A", "attributes": { "label": "A", "type": "Event" } },
      { "key": "B", "attributes": { "label": "B", "type": "Function" } }
    ],
    "edges": [{ "key": "aToB", "source": "A", "target": "B", "attributes": {} }]
  },
  "rules": [{
    "key": "find_node",
    "patternGraph": {
      "options": { "type": "directed" },
      "nodes": [{ "key": "A", "attributes": {} }],
      "edges": []
    }
  }]
}
EOF

    # 1. Node CRUD
    cli_ok "cli: create-node"   '"key"'    create-node "$tmpdir/node1.json"
    cli_ok "cli: create-node 2" '"key"'    create-node "$tmpdir/node2.json"
    cli_ok "cli: get-nodes"     'cliNode1' get-nodes
    cli_ok "cli: get-node"      '"label"'  get-node "cliNode1"

    # 2. Edge CRUD
    cli_ok "cli: create-edge"   '"key"'    create-edge "$tmpdir/edge.json"
    cli_ok "cli: get-edge"      '"key"'    get-edge "cliEdge1"

    # 3. Graph transformation (stateless — operates on provided hostgraph)
    cli_ok "cli: transform"     'NewNode'  transform "$tmpdir/transform.json"
    cli_ok "cli: find"          'nodes'    find      "$tmpdir/find.json"

    # 4. Cleanup
    cli_ok "cli: delete-edge"   ''         delete-edge  "cliEdge1"
    cli_ok "cli: delete-node"   ''         delete-node  "cliNode1"
    cli_ok "cli: delete-nodes"  ''         delete-nodes

    rm -rf "$tmpdir"
}

# ---- main ------------------------------------------------------------------

echo "graph-rewriting-service smoke tests"
echo "  BASE_URL: ${BASE_URL}"

# Always rebuild dist to ensure latest code is used
echo "  Building dist/..."
npm run build

memory_tests
neo4j_tests
cli_tests

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "Results: ${PASS} passed, ${FAIL} failed"
echo "════════════════════════════════════════════════════════════════════════"

[[ "$FAIL" -eq 0 ]]
