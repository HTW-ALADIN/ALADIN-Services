#!/usr/bin/env bash
# Smoke test for the edit-distance-service
# Tests all text and graph algorithms via HTTP API

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0

green() { echo -e "\033[32m$1\033[0m"; }
red() { echo -e "\033[31m$1\033[0m"; }

test_endpoint() {
    local name="$1"
    local method="$2"
    local url="$3"
    local data="$4"
    local expected_status="$5"

    if [ "$method" = "GET" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$url" 2>/dev/null || true)
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$data" "$BASE_URL$url" 2>/dev/null || true)
    fi

    if [ "$response" = "$expected_status" ]; then
        green "PASS: $name"
        PASS=$((PASS + 1))
    else
        red "FAIL: $name (expected $expected_status, got $response)"
        FAIL=$((FAIL + 1))
    fi
}

echo "============================================"
echo "  Edit Distance Service - Smoke Tests"
echo "  Base URL: $BASE_URL"
echo "============================================"
echo ""

# Health
test_endpoint "Health" "GET" "/health" "" "200"

# Discovery
test_endpoint "List text algorithms" "GET" "/v1/text/algorithms" "" "200"
test_endpoint "List GED algorithms" "GET" "/v1/graphs/ged/algorithms" "" "200"

# Text ED - Tier 1 (RapidFuzz + textdistance + jellyfish)
test_endpoint "Levenshtein (RapidFuzz)" "POST" "/v1/text/compare" \
    '{"algorithm":"levenshtein","backend":"rapidfuzz","params":{},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}' "200"

test_endpoint "Levenshtein (textdistance)" "POST" "/v1/text/compare" \
    '{"algorithm":"levenshtein","backend":"textdistance","params":{},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}' "200"

test_endpoint "Levenshtein (jellyfish)" "POST" "/v1/text/compare" \
    '{"algorithm":"levenshtein","backend":"jellyfish","params":{},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}' "200"

test_endpoint "Damerau-Levenshtein (RapidFuzz)" "POST" "/v1/text/compare" \
    '{"algorithm":"damerau_levenshtein","backend":"rapidfuzz","params":{},"inputs":[{"id":"p1","a":"jellyfish","b":"jellyfihs"}]}' "200"

test_endpoint "Hamming (RapidFuzz)" "POST" "/v1/text/compare" \
    '{"algorithm":"hamming","backend":"rapidfuzz","params":{},"inputs":[{"id":"p1","a":"karolin","b":"kathrin"}]}' "200"

test_endpoint "Jaro-Winkler (RapidFuzz)" "POST" "/v1/text/compare" \
    '{"algorithm":"jaro_winkler","backend":"rapidfuzz","params":{},"inputs":[{"id":"p1","a":"MARTHA","b":"MARHTA"}]}' "200"

test_endpoint "OSA (RapidFuzz)" "POST" "/v1/text/compare" \
    '{"algorithm":"osa","backend":"rapidfuzz","params":{},"inputs":[{"id":"p1","a":"ca","b":"abc"}]}' "200"

test_endpoint "Indel (RapidFuzz)" "POST" "/v1/text/compare" \
    '{"algorithm":"indel","backend":"rapidfuzz","params":{},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}' "200"

# Text ED - textdistance-only algorithms
test_endpoint "LCS (textdistance)" "POST" "/v1/text/compare" \
    '{"algorithm":"lcs","backend":"textdistance","params":{},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}' "200"

test_endpoint "Needleman-Wunsch (textdistance)" "POST" "/v1/text/compare" \
    '{"algorithm":"needleman_wunsch","backend":"textdistance","params":{"gap_cost":1.0},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}' "200"

test_endpoint "Smith-Waterman (textdistance)" "POST" "/v1/text/compare" \
    '{"algorithm":"smith_waterman","backend":"textdistance","params":{},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}' "200"

test_endpoint "Token set similarity (textdistance)" "POST" "/v1/text/compare" \
    '{"algorithm":"token_set_similarity","backend":"textdistance","params":{"metric":"jaccard"},"inputs":[{"id":"p1","a":"hello world","b":"world hello"}]}' "200"

test_endpoint "NCD (textdistance)" "POST" "/v1/text/compare" \
    '{"algorithm":"ncd","backend":"textdistance","params":{"qval":1,"compressor":"zlib"},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}' "200"

# Text ED - jellyfish phonetic
test_endpoint "Phonetic encoding (jellyfish)" "POST" "/v1/text/compare" \
    '{"algorithm":"phonetic_encoding","backend":"jellyfish","params":{"scheme":"soundex"},"inputs":[{"id":"w1","text":"Jellyfish"}]}' "200"

# Text ED - Tier 2 (edlib + diff-match-patch)
test_endpoint "Long sequence alignment (edlib)" "POST" "/v1/text/compare" \
    '{"algorithm":"long_sequence_alignment","backend":"edlib","params":{"mode":"NW","task":"distance"},"inputs":[{"id":"p1","a":"kitten","b":"sitting"}]}' "200"

test_endpoint "Diff/Patch (diff-match-patch)" "POST" "/v1/text/compare" \
    '{"algorithm":"diff_patch","backend":"diff_match_patch","params":{},"inputs":[{"id":"p1","a":"The quick brown fox","b":"The slow brown fox"}]}' "200"

# Graph ED
test_endpoint "GED A* (NetworkX)" "POST" "/v1/graphs/ged/compute" \
    '{"algorithm":"ged_astar","backend":"networkx","params":{"mode":"exact","timeout_ms":5000},"graphs":[{"id":"pair-1","g1":{"nodes":[{"id":"A"},{"id":"B"}],"edges":[{"source":"A","target":"B"}]},"g2":{"nodes":[{"id":"A"},{"id":"B"},{"id":"C"}],"edges":[{"source":"A","target":"B"},{"source":"B","target":"C"}]}}]}' "201"

test_endpoint "GED A* (NetworkX, anytime)" "POST" "/v1/graphs/ged/compute" \
    '{"algorithm":"ged_astar","backend":"networkx","params":{"mode":"anytime","timeout_ms":3000},"graphs":[{"id":"pair-1","g1":{"nodes":[{"id":"1"},{"id":"2"}],"edges":[{"source":"1","target":"2"}]},"g2":{"nodes":[{"id":"1"},{"id":"2"},{"id":"3"}],"edges":[{"source":"1","target":"2"},{"source":"2","target":"3"}]}}]}' "201"

# Batch text comparison
test_endpoint "Batch text compare" "POST" "/v1/text/compare" \
    '{"algorithm":"levenshtein","backend":"rapidfuzz","params":{},"inputs":[{"id":"p1","a":"kitten","b":"sitting"},{"id":"p2","a":"flaw","b":"lawn"}]}' "200"

# Error cases
test_endpoint "Missing algorithm (400)" "POST" "/v1/text/compare" \
    '{"inputs":[{"id":"p1","a":"a","b":"b"}]}' "400"

echo ""
echo "============================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "============================================"

exit $FAIL