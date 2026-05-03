#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# smoke-test.sh — End-to-end smoke tests for sql-assessment-service
#
# Usage:
#   ./scripts/smoke-test.sh [BASE_URL]
#
# Environment variables:
#   BASE_URL          Service base URL  (default: http://localhost:3000)
#
# PGlite path (no external DB needed):
#   PGLITE_DB_ID          databaseId to use  (default: smoke-db)
#
# Init-SQL-file feature (optional — tests the PGLITE_INIT_SQL_FILE / --init-sql-file feature):
#   SMOKE_TEST_INIT_SQL   Set to '1' to enable (server must be started with PGLITE_INIT_SQL_FILE
#                         pointing to a valid .sql file containing at least one table)
#   SMOKE_INIT_SQL_TABLE  A table name that exists in the configured init SQL file
#                         (default: products)  — used to verify the file was actually loaded
#
# PostgreSQL path (optional — skipped if PG_HOST is not set):
#   PG_HOST           Postgres host
#   PG_PORT           Postgres port       (default: 5432)
#   PG_USER           Postgres username
#   PG_PASSWORD       Postgres password
#   PG_DATABASE       Postgres database name
#   PG_SCHEMA         Postgres schema     (default: public)
#
# Exit code: 0 = all tests passed, 1 = one or more failures
# ---------------------------------------------------------------------------
set -euo pipefail

BASE_URL="${1:-${BASE_URL:-http://localhost:3000}}"
PGLITE_DB_ID="${PGLITE_DB_ID:-smoke-db}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_PATH="$(dirname "$SCRIPT_DIR")/build/cli/index.js"

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

# Sends a POST request, prints body+status, calls assert.
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

# Like post, but also asserts that the response body contains NEEDLE.
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

# Runs the CLI in-process; checks exit code.
# Usage: cli_invoke LABEL EXPECTED_EXIT [CLI_ARGS...]
cli_invoke() {
    local label="$1" expected_exit="$2"
    shift 2
    local output exit_code=0
    output=$(node "$CLI_PATH" "$@" 2>&1) || exit_code=$?
    if [[ "$exit_code" -eq "$expected_exit" ]]; then
        green "  PASS  [exit=$exit_code] $label"
        (( PASS++ )) || true
    else
        red   "  FAIL  [exit=$exit_code != $expected_exit] $label"
        red   "         output: $output"
        (( FAIL++ )) || true
    fi
}

# Like cli_invoke but also asserts that output contains NEEDLE.
# Usage: cli_invoke_contains LABEL EXPECTED_EXIT NEEDLE [CLI_ARGS...]
cli_invoke_contains() {
    local label="$1" expected_exit="$2" needle="$3"
    shift 3
    local output exit_code=0
    output=$(node "$CLI_PATH" "$@" 2>&1) || exit_code=$?
    if [[ "$exit_code" -eq "$expected_exit" ]]; then
        green "  PASS  [exit=$exit_code] $label"
        (( PASS++ )) || true
    else
        red   "  FAIL  [exit=$exit_code != $expected_exit] $label"
        red   "         output: $output"
        (( FAIL++ )) || true
        return
    fi
    if echo "$output" | grep -q "$needle"; then
        green "  PASS  output contains \"$needle\""
        (( PASS++ )) || true
    else
        red   "  FAIL  output does not contain \"$needle\""
        red   "         output: $output"
        (( FAIL++ )) || true
    fi
}

# ---- PGlite tests ----------------------------------------------------------

pglite_tests() {
    echo ""
    echo "── PGlite path (${BASE_URL}) ──────────────────────────────────────────"

    local DDL
    DDL='CREATE TABLE products (id SERIAL PRIMARY KEY, name TEXT NOT NULL, price NUMERIC(10,2));
CREATE TABLE orders (id SERIAL PRIMARY KEY, product_id INTEGER REFERENCES products(id), quantity INTEGER NOT NULL);
INSERT INTO products (name, price) VALUES ('\''Widget'\'', 9.99), ('\''Gadget'\'', 19.99);
INSERT INTO orders (product_id, quantity) VALUES (1, 5), (2, 3);'

    # 1. Register DB
    post "analyze-database — valid DDL" "200" \
        "${BASE_URL}/api/database/analyze-database" \
        "$(jq -n --arg id "$PGLITE_DB_ID" --arg sql "$DDL" \
            '{connectionInfo:{type:"pglite",databaseId:$id,sqlContent:$sql}}')"

    # 2. Simple SELECT
    post "execute — SELECT *" "200" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --arg id "$PGLITE_DB_ID" \
            '{connectionInfo:{type:"pglite",databaseId:$id},query:"SELECT * FROM products ORDER BY id"}')"

    # 3. JOIN
    post "execute — JOIN" "200" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --arg id "$PGLITE_DB_ID" \
            '{connectionInfo:{type:"pglite",databaseId:$id},query:"SELECT p.name, o.quantity FROM products p JOIN orders o ON p.id = o.product_id ORDER BY p.id"}')"

    # 4. WHERE + filter
    post "execute — WHERE no results" "200" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --arg id "$PGLITE_DB_ID" \
            '{connectionInfo:{type:"pglite",databaseId:$id},query:"SELECT * FROM products WHERE name = '\''NoSuchProduct'\''"}')"

    # 5. INSERT rejected
    post "execute — INSERT (expect 400 NON_SELECT)" "400" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --arg id "$PGLITE_DB_ID" \
            '{connectionInfo:{type:"pglite",databaseId:$id},query:"INSERT INTO products (name, price) VALUES ('"'"'X'"'"', 1.0)"}')"

    # 6. DELETE rejected
    post "execute — DELETE (expect 400 NON_SELECT)" "400" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --arg id "$PGLITE_DB_ID" \
            '{connectionInfo:{type:"pglite",databaseId:$id},query:"DELETE FROM products"}')"

    # 7. Non-existent table → 500
    post "execute — unknown table (expect 500)" "500" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --arg id "$PGLITE_DB_ID" \
            '{connectionInfo:{type:"pglite",databaseId:$id},query:"SELECT * FROM no_such_table"}')"

    # 8. Missing sqlContent → 400 when no init file; 200 when init file is configured
    if [[ -z "${SMOKE_TEST_INIT_SQL:-}" ]]; then
        post "analyze-database — missing sqlContent (expect 400)" "400" \
            "${BASE_URL}/api/database/analyze-database" \
            "$(jq -n --arg id "$PGLITE_DB_ID" \
                '{connectionInfo:{type:"pglite",databaseId:$id}}')"
    else
        post "analyze-database — missing sqlContent (init-file provides it, expect 200)" "200" \
            "${BASE_URL}/api/database/analyze-database" \
            "$(jq -n --arg id "$PGLITE_DB_ID" \
                '{connectionInfo:{type:"pglite",databaseId:$id}}')"
    fi

    # 9. Missing databaseId → 400
    post "analyze-database — missing databaseId (expect 400)" "400" \
        "${BASE_URL}/api/database/analyze-database" \
        '{"connectionInfo":{"type":"pglite","sqlContent":"SELECT 1"}}'

    # 10. Unregistered databaseId → 400 (only when no init-SQL file is configured,
    #     because an init file auto-initialises any unknown databaseId)
    if [[ -z "${SMOKE_TEST_INIT_SQL:-}" ]]; then
        post "execute — unregistered databaseId (expect 400)" "400" \
            "${BASE_URL}/api/query/execute" \
            '{"connectionInfo":{"type":"pglite","databaseId":"__not_registered__"},"query":"SELECT 1"}'
    else
        green "  SKIP  execute — unregistered databaseId (init-SQL-file auto-initialises any databaseId)"
    fi

    # 11. Re-register with different schema (replace)
    post "analyze-database — replace existing instance" "200" \
        "${BASE_URL}/api/database/analyze-database" \
        "$(jq -n --arg id "$PGLITE_DB_ID" \
            '{connectionInfo:{type:"pglite",databaseId:$id,sqlContent:"CREATE TABLE categories (id SERIAL PRIMARY KEY, label TEXT NOT NULL);"}}')"

    post "execute — query new schema after replace" "200" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --arg id "$PGLITE_DB_ID" \
            '{connectionInfo:{type:"pglite",databaseId:$id},query:"SELECT * FROM categories"}')"
}

# ---- Init-SQL-file tests (optional) ---------------------------------------

pglite_init_sql_file_tests() {
    if [[ -z "${SMOKE_TEST_INIT_SQL:-}" ]]; then
        echo ""
        echo "── PGlite init-SQL-file tests — skipped (set SMOKE_TEST_INIT_SQL=1 to enable) ─"
        return
    fi

    echo ""
    echo "── PGlite init-SQL-file feature ────────────────────────────────────────"
    echo "   (server must be started with PGLITE_INIT_SQL_FILE set to a valid file)"

    local INIT_TABLE="${SMOKE_INIT_SQL_TABLE:-products}"
    local NEW_DB="smoke-init-${RANDOM}"
    local OVERRIDE_DB="smoke-override-${RANDOM}"

    # 1. Fresh databaseId without sqlContent — init file provides the schema
    post "init-sql-file — fresh databaseId, no sqlContent (expect 200)" "200" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --arg id "$NEW_DB" \
            '{connectionInfo:{type:"pglite",databaseId:$id},query:"SELECT 1 AS ping"}')" 

    # 2. The init-file schema is actually usable (query a known table)
    post "init-sql-file — query table from init file (expect 200)" "200" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --arg id "$NEW_DB" --arg tbl "$INIT_TABLE" \
            '{connectionInfo:{type:"pglite",databaseId:$id},query:("SELECT * FROM "+$tbl+" LIMIT 1")}')" 

    # 3. Explicit sqlContent overrides the init file
    post "init-sql-file — explicit sqlContent takes priority (expect 200)" "200" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --arg id "$OVERRIDE_DB" \
            '{connectionInfo:{type:"pglite",databaseId:$id,sqlContent:"CREATE TABLE override_tbl (id SERIAL PRIMARY KEY);"},query:"SELECT * FROM override_tbl"}')" 

    # 4. analyze-database without sqlContent — init file counts as the schema
    post "init-sql-file — analyze-database without sqlContent (expect 200)" "200" \
        "${BASE_URL}/api/database/analyze-database" \
        "$(jq -n --arg id "smoke-analyze-${RANDOM}" \
            '{connectionInfo:{type:"pglite",databaseId:$id}}')" 
}

# ---- CLI tests ------------------------------------------------------------

cli_tests() {
    echo ""
    echo "── CLI tests (build/cli/index.js) ──────────────────────────────────────"

    if [[ ! -f "$CLI_PATH" ]]; then
        red "  SKIP  CLI binary not found at ${CLI_PATH} — run 'npm run build'"
        return
    fi

    local CLI_DB_ID="cli-smoke-db"

    local DDL
    DDL='CREATE TABLE products (id SERIAL PRIMARY KEY, name TEXT NOT NULL, price NUMERIC(10,2));
CREATE TABLE orders (id SERIAL PRIMARY KEY, product_id INTEGER REFERENCES products(id), quantity INTEGER NOT NULL);
INSERT INTO products (name, price) VALUES ('\''Widget'\'', 9.99), ('\''Gadget'\'', 19.99);
INSERT INTO orders (product_id, quantity) VALUES (1, 5), (2, 3);'

    local DDL_PRODUCTS_ONLY
    DDL_PRODUCTS_ONLY='CREATE TABLE products (id SERIAL PRIMARY KEY, name TEXT NOT NULL, price NUMERIC(10,2));
INSERT INTO products (name, price) VALUES ('\''Widget'\'', 9.99), ('\''Gadget'\'', 19.99);'

    # 1. --list shows available commands
    cli_invoke_contains "--list shows commands" 0 "database:analyze-database" \
        --list

    # 2. --help shows usage text
    cli_invoke_contains "--help shows usage" 0 "Usage:" \
        --help

    # 3. Unknown command → exit 1
    cli_invoke "unknown command (→ exit 1)" 1 \
        no:such:command '{"foo":"bar"}'

    # 4. analyze-database — valid DDL via inline JSON arg
    cli_invoke "database:analyze-database — valid DDL" 0 \
        database:analyze-database \
        "$(jq -n --arg id "$CLI_DB_ID" --arg sql "$DDL" \
            '{connectionInfo:{type:"pglite",databaseId:$id,sqlContent:$sql}}')"

    # 5. query:execute — SELECT * (sqlContent provided inline so process is self-contained)
    cli_invoke_contains "query:execute — SELECT * FROM products" 0 "Widget" \
        query:execute \
        "$(jq -n --arg id "$CLI_DB_ID" --arg sql "$DDL_PRODUCTS_ONLY" \
            '{connectionInfo:{type:"pglite",databaseId:$id,sqlContent:$sql},query:"SELECT * FROM products ORDER BY id"}')"

    # 6. query:execute — JOIN (both tables in sqlContent)
    cli_invoke "query:execute — JOIN products + orders" 0 \
        query:execute \
        "$(jq -n --arg id "$CLI_DB_ID" --arg sql "$DDL" \
            '{connectionInfo:{type:"pglite",databaseId:$id,sqlContent:$sql},query:"SELECT p.name, o.quantity FROM products p JOIN orders o ON p.id = o.product_id ORDER BY p.id"}')"

    # 7. INSERT rejected → exit 1
    cli_invoke "query:execute — INSERT (NON_SELECT → exit 1)" 1 \
        query:execute \
        "$(jq -n --arg id "$CLI_DB_ID" --arg sql "$DDL_PRODUCTS_ONLY" --arg q "INSERT INTO products (name, price) VALUES ('X', 1.0)" \
            '{connectionInfo:{type:"pglite",databaseId:$id,sqlContent:$sql},query:$q}')"

    # 8. Unknown table → exit 1
    cli_invoke "query:execute — unknown table (→ exit 1)" 1 \
        query:execute \
        "$(jq -n --arg id "$CLI_DB_ID" --arg sql "$DDL_PRODUCTS_ONLY" \
            '{connectionInfo:{type:"pglite",databaseId:$id,sqlContent:$sql},query:"SELECT * FROM no_such_table"}')"

    # 9. Body via stdin pipe (auto-detected when stdin is not a TTY)
    local stdin_body stdin_out stdin_exit=0
    stdin_body=$(jq -n --arg id "$CLI_DB_ID" --arg sql "$DDL_PRODUCTS_ONLY" \
        '{connectionInfo:{type:"pglite",databaseId:$id,sqlContent:$sql},query:"SELECT name FROM products WHERE price > 15 ORDER BY id"}')
    stdin_out=$(echo "$stdin_body" | node "$CLI_PATH" query:execute 2>&1) || stdin_exit=$?
    if [[ "$stdin_exit" -eq 0 ]]; then
        green "  PASS  [exit=0] query:execute — body via stdin pipe"
        (( PASS++ )) || true
        if echo "$stdin_out" | grep -q "Gadget"; then
            green "  PASS  output contains \"Gadget\""
            (( PASS++ )) || true
        else
            red   "  FAIL  output does not contain \"Gadget\""
            red   "         output: $stdin_out"
            (( FAIL++ )) || true
        fi
    else
        red   "  FAIL  [exit=$stdin_exit != 0] query:execute — body via stdin pipe"
        red   "         output: $stdin_out"
        (( FAIL++ )) || true
    fi

    # 10. Body via -f file
    local tmp_body
    tmp_body=$(mktemp /tmp/cli-smoke-XXXXXX.json)
    jq -n --arg id "$CLI_DB_ID" --arg sql "$DDL_PRODUCTS_ONLY" \
        '{connectionInfo:{type:"pglite",databaseId:$id,sqlContent:$sql},query:"SELECT COUNT(*) AS cnt FROM products"}' \
        > "$tmp_body"
    cli_invoke_contains "query:execute — body via -f file" 0 "cnt" \
        query:execute -f "$tmp_body"
    rm -f "$tmp_body"

    # 11. Missing databaseId → exit 1
    cli_invoke "database:analyze-database — missing databaseId (→ exit 1)" 1 \
        database:analyze-database \
        '{"connectionInfo":{"type":"pglite","sqlContent":"SELECT 1"}}'

    # 12. --init-sql-file flag: command must come first, flag comes after the JSON body
    if [[ -n "${SMOKE_TEST_INIT_SQL:-}" && -n "${PGLITE_INIT_SQL_FILE:-}" ]]; then
        local INIT_TABLE="${SMOKE_INIT_SQL_TABLE:-products}"
        local FRESH_DB="cli-init-${RANDOM}"
        local INIT_QUERY="SELECT * FROM ${INIT_TABLE} LIMIT 1"
        cli_invoke_contains \
            "query:execute — --init-sql-file, query table from init file" 0 "rows" \
            query:execute \
            "$(jq -n --arg id "$FRESH_DB" --arg q "$INIT_QUERY" \
                '{connectionInfo:{type:"pglite",databaseId:$id},query:$q}')" \
            --init-sql-file "$PGLITE_INIT_SQL_FILE"
    elif [[ -n "${SMOKE_TEST_INIT_SQL:-}" ]]; then
        echo "  SKIP  CLI --init-sql-file test (set PGLITE_INIT_SQL_FILE to enable)"
    fi
}

# ---- PostgreSQL tests (optional) -------------------------------------------

postgres_tests() {
    if [[ -z "${PG_HOST:-}" ]]; then
        echo ""
        echo "── PostgreSQL path — skipped (PG_HOST not set) ────────────────────────"
        return
    fi

    echo ""
    echo "── PostgreSQL path (${PG_HOST}:${PG_PORT:-5432}) ─────────────────────────"

    local CONN
    CONN=$(jq -n \
        --arg host "${PG_HOST}" \
        --argjson port "${PG_PORT:-5432}" \
        --arg user "${PG_USER:-postgres}" \
        --arg pass "${PG_PASSWORD:-}" \
        --arg db   "${PG_DATABASE:-postgres}" \
        --arg schema "${PG_SCHEMA:-public}" \
        '{type:"postgres",host:$host,port:$port,username:$user,password:$pass,database:$db,schema:$schema}')

    post "analyze-database — valid PG connection" "200" \
        "${BASE_URL}/api/database/analyze-database" \
        "$(jq -n --argjson conn "$CONN" '{connectionInfo:$conn}')"

    post "execute — SELECT 1" "200" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --argjson conn "$CONN" '{connectionInfo:$conn,query:"SELECT 1 AS value"}')"

    # Prove we are actually talking to PostgreSQL (pg-specific system function)
    post_body_contains "execute — version() contains 'PostgreSQL'" "200" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --argjson conn "$CONN" '{connectionInfo:$conn,query:"SELECT version() AS ver"}')" \
        "PostgreSQL"

    # Prove backup.sql was loaded — pg_catalog.pg_tables lists aladin-owned tables
    post_body_contains "execute — pg_tables shows backup.sql tables (angest)" "200" \
        "${BASE_URL}/api/query/execute" \
        "$(jq -n --argjson conn "$CONN" \
            '{connectionInfo:$conn,query:"SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='"'"'public'"'"' ORDER BY tablename"}')" \
        "angest"
}

# ---- main ------------------------------------------------------------------

echo "sql-assessment-service smoke tests"
echo "  BASE_URL: ${BASE_URL}"

# Wait for service to be reachable (up to 10 s)
echo -n "  Waiting for service..."
for i in $(seq 1 10); do
    if curl -sf "${BASE_URL}/api/health" >/dev/null 2>&1 || \
       curl -sf -o /dev/null -w '%{http_code}' "${BASE_URL}/" 2>/dev/null | grep -qE '^[0-9]'; then
        break
    fi
    # Try any endpoint — a 404 still means the server is up
    code=$(curl -s -o /dev/null -w '%{http_code}' "${BASE_URL}/api/query/execute" 2>/dev/null || true)
    if [[ "$code" =~ ^[0-9]+$ && "$code" != "000" ]]; then
        break
    fi
    echo -n "."
    sleep 1
done
echo " OK"

pglite_tests
pglite_init_sql_file_tests
postgres_tests
cli_tests

echo ""
echo "────────────────────────────────────────────────"
echo "Results: ${PASS} passed, ${FAIL} failed"
echo "────────────────────────────────────────────────"

[[ "$FAIL" -eq 0 ]]
