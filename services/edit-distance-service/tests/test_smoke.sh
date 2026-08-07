#!/usr/bin/env bash
# Smoke tests for the edit-distance-service.
# Usage: bash tests/test_smoke.sh <base_url>
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0

green() { printf "\033[32m%s\033[0m\n" "$1"; }
red()   { printf "\033[31m%s\033[0m\n" "$1"; }

check() {
    local label="$1" result="$2"
    if [[ "$result" == "0" ]]; then
        green "  ✓ $label"
        ((PASS++))
    else
        red "  ✗ $label"
        ((FAIL++))
    fi
}

echo "=== Smoke Tests for edit-distance-service ==="

# --- Health ---
curl -sf "$BASE_URL/health" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['status']=='ok'" && rc=0 || rc=$?
check "Health endpoint" "$rc"

# --- Text algorithms discovery ---
curl -sf "$BASE_URL/v1/text/algorithms" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d)>0" && rc=0 || rc=$?
check "Text algorithms discovery" "$rc"

# --- GED algorithms discovery ---
curl -sf "$BASE_URL/v1/graphs/algorithms" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d)>0" && rc=0 || rc=$?
check "GED algorithms discovery" "$rc"

# --- Levenshtein compute ---
curl -sf -X POST "$BASE_URL/v1/text/distance" \
    -H 'Content-Type: application/json' \
    -d '{"algorithm":"levenshtein","params":{},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['algorithm']=='levenshtein'; assert len(d['results'])==1" && rc=0 || rc=$?
check "Levenshtein compute" "$rc"

# --- Phonetic encoding ---
curl -sf -X POST "$BASE_URL/v1/text/distance" \
    -H 'Content-Type: application/json' \
    -d '{"algorithm":"phonetic_encoding","params":{"scheme":"soundex"},"inputs":[{"id":"w1","text":"Jellyfish"}]}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['result_type']=='phonetic_code'" && rc=0 || rc=$?
check "Phonetic encoding" "$rc"

# --- GED compute (NetworkX) ---
curl -sf -X POST "$BASE_URL/v1/graphs/distance" \
    -H 'Content-Type: application/json' \
    -d '{"algorithm":"ged_astar","params":{"mode":"exact","timeout_ms":5000},"graphs":[{"id":"p1","g1":{"nodes":[{"id":"A"},{"id":"B"}],"edges":[{"source":"A","target":"B"}]},"g2":{"nodes":[{"id":"A"},{"id":"B"},{"id":"C"}],"edges":[{"source":"A","target":"B"},{"source":"B","target":"C"}]}}]}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['algorithm']=='ged_astar'; assert len(d['results'])==1" && rc=0 || rc=$?
check "GED compute (NetworkX)" "$rc"

# --- Diff/patch ---
curl -sf -X POST "$BASE_URL/v1/text/distance" \
    -H 'Content-Type: application/json' \
    -d '{"algorithm":"diff_patch","params":{},"inputs":[{"id":"p1","a":"The quick brown fox","b":"The slow brown fox"}]}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['result_type']=='edit_script'" && rc=0 || rc=$?
check "Diff/patch compute" "$rc"

# --- Summary ---
echo "------------------------"
echo "Passed: $PASS  Failed: $FAIL"
echo "------------------------"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi