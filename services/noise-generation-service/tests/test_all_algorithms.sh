#!/bin/bash
# =============================================================================
# Smoke Tests for the Noise Generation Service
#
# Every test calls POST /v1/noise and validates the full JSON response,
# which includes: id, status, algorithm, data (full grid), and size.
# There are no separate GET endpoints anymore.
# =============================================================================

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0

check_response() {
    local response="$1"
    local expected_alg="$2"

    local alg
    alg=$(echo "$response" | jq -r '.algorithm')
    local status
    status=$(echo "$response" | jq -r '.status')
    local has_id
    has_id=$(echo "$response" | jq 'has("id")')
    local has_data
    has_data=$(echo "$response" | jq 'has("data")')
    local has_size
    has_size=$(echo "$response" | jq 'has("size")')

    if [[ "$alg" != "$expected_alg" ]]; then
        echo "  ❌ FAIL: algorithm mismatch (got '$alg', expected '$expected_alg')"
        return 1
    fi
    if [[ "$status" != "completed" ]]; then
        echo "  ❌ FAIL: status is '$status', expected 'completed'"
        return 1
    fi
    if [[ "$has_id" != "true" ]]; then
        echo "  ❌ FAIL: missing 'id' field"
        return 1
    fi
    if [[ "$has_data" != "true" ]]; then
        echo "  ❌ FAIL: missing 'data' field (full grid)"
        return 1
    fi
    if [[ "$has_size" != "true" ]]; then
        echo "  ❌ FAIL: missing 'size' field"
        return 1
    fi
    echo "  ✅ PASS"
    return 0
}

run_test() {
    local test_name="$1"
    local expected_alg="$2"
    local payload="$3"

    echo ""
    echo "▸ $test_name"

    local response
    response=$(curl -s -X POST "$BASE_URL/v1/noise" \
        -H "Content-Type: application/json" \
        -d "$payload")

    # Check HTTP / JSON validity (e.g. server down or invalid payload)
    if echo "$response" | jq -e . >/dev/null 2>&1; then
        if check_response "$response" "$expected_alg"; then
            PASS=$((PASS + 1))
        else
            echo "  Response: $(echo "$response" | jq -c '{id, algorithm, status, size}')"
            FAIL=$((FAIL + 1))
        fi
    else
        echo "  ❌ FAIL: invalid JSON — is the server running?"
        echo "  Response: $response"
        FAIL=$((FAIL + 1))
    fi
}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Noise Generation Service — Full Smoke Test Suite           ║"
echo "║  Target: $BASE_URL"
echo "╚══════════════════════════════════════════════════════════════╝"

# ──────────── Core Noise Algorithms ────────────

# Test 1: Perlin (fastnoise_lite)
# Verifies basic Perlin noise generation using the default backend
run_test \
    "Perlin (fastnoise_lite)" \
    "perlin" \
    '{"algorithm":"perlin","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 2: Perlin (noise_rs backend)
# Verifies Perlin noise with alternative backend -> same algorithm, different implementation
run_test \
    "Perlin (noise_rs)" \
    "perlin" \
    '{"algorithm":"perlin","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 3: Simplex (noise_rs only)
# Verifies Simplex noise — improved visual quality with reduced computational complexity
run_test \
    "Simplex (noise_rs)" \
    "simplex" \
    '{"algorithm":"simplex","params":{"seed":123},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 4: OpenSimplex2 (fastnoise_lite)
# Verifies OpenSimplex2 — modern variant with better visual quality
run_test \
    "OpenSimplex2 (fastnoise_lite)" \
    "opensimplex2" \
    '{"algorithm":"opensimplex2","params":{"seed":456},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 5: OpenSimplex2 (noise_rs)
# Verifies OpenSimplex2 with alternative backend
run_test \
    "OpenSimplex2 (noise_rs)" \
    "opensimplex2" \
    '{"algorithm":"opensimplex2","params":{"seed":456},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 6: SuperSimplex (noise_rs only)
# Verifies SuperSimplex — higher-dimensional noise variant
run_test \
    "SuperSimplex (noise_rs)" \
    "supersimplex" \
    '{"algorithm":"supersimplex","params":{"seed":789},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 7: Value noise (default backend)
# Verifies grid-based Value noise with cubic interpolation
run_test \
    "Value (fastnoise_lite)" \
    "value" \
    '{"algorithm":"value","params":{"seed":111},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 8: Cellular / Worley (fastnoise_lite)
# Verifies cell-based patterns (Voronoi/Worley) — default parameters
run_test \
    "Cellular (fastnoise_lite)" \
    "cellular" \
    '{"algorithm":"cellular","params":{"seed":222},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# ──────────── Fractal Algorithms ────────────

# Test 9: FBM (Fractal Brownian Motion)
# Verifies multi-octave fractal noise with octaves, frequency, lacunarity & persistence
run_test \
    "FBM (noise_rs)" \
    "fbm" \
    '{"algorithm":"fbm","params":{"seed":333,"octaves":4,"frequency":0.1,"lacunarity":2.0,"persistence":0.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 10: Billow (noise_rs only)
# Verifies Billow noise (absolute value of Perlin) — produces soft, cloud-like structures
run_test \
    "Billow (noise_rs)" \
    "billow" \
    '{"algorithm":"billow","params":{"seed":444,"octaves":3},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 11: Ridged Multi (fastnoise_lite)
# Verifies ridge-like fractal patterns with sharp ridges
run_test \
    "RidgedMulti (fastnoise_lite)" \
    "ridged_multi" \
    '{"algorithm":"ridged_multi","params":{"seed":555,"octaves":4},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 12: Hybrid Multi (noise_rs only)
# Verifies Hybrid Multi-fractal noise — combination of multiple noise types
run_test \
    "HybridMulti (noise_rs)" \
    "hybrid_multi" \
    '{"algorithm":"hybrid_multi","params":{"seed":666,"octaves":4},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 13: PingPong (fastnoise_lite only)
# Verifies PingPong fractal with folding effect controlled via "strength" parameter
run_test \
    "PingPong (fastnoise_lite)" \
    "pingpong" \
    '{"algorithm":"pingpong","params":{"seed":777,"strength":2.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# ──────────── Advanced Algorithms ────────────

# Test 14: Domain Warp (fastnoise_lite only)
# Verifies Domain Warping — coordinate transformation for organic distortion effects
run_test \
    "Domain Warp (fastnoise_lite)" \
    "domain_warp" \
    '{"algorithm":"domain_warp","params":{"seed":888,"amplitude":1.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 15: Combinator (Add)
# Verifies generic combinators — combining two noise sources via "add"
run_test \
    "Combinator (Add)" \
    "combinator" \
    '{"algorithm":"combinator","params":{"seed":999,"op":"add"},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 16: Utility (Constant)
# Verifies deterministic utility generators — constant value of 0.5 across the entire grid
run_test \
    "Utility (Constant)" \
    "utility" \
    '{"algorithm":"utility","params":{"kind":"constant","value":0.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 17: White Noise (native)
# Verifies native white noise implementation — pure hash-based randomness without interpolation grid
run_test \
    "White Noise (native)" \
    "white" \
    '{"algorithm":"white","params":{"seed":1010},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# ──────────── Response Validation Tests ────────────

# Test 18: Verifies that the response contains the full data grid
echo ""
echo "▸ Response format check: Full data grid (4×4)"
response=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":7},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}')
data_rows=$(echo "$response" | jq '.data | length')
data_cols=$(echo "$response" | jq '.data[0] | length')
size_field=$(echo "$response" | jq -c '.size')
if [[ "$data_rows" -eq 4 && "$data_cols" -eq 4 && "$size_field" == "[4,4]" ]]; then
    echo "  ✅ PASS (data=${data_rows}×${data_cols}, size=${size_field})"
    PASS=$((PASS + 1))
else
    echo "  ❌ FAIL: expected 4×4 grid, got data=${data_rows}×${data_cols}, size=${size_field}"
    FAIL=$((FAIL + 1))
fi

# Test 19: Verifies that different seeds generate different data
echo ""
echo "▸ Deterministic seed check: Seed 1 ≠ Seed 2 (Perlin 4×4)"
r1=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":1},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -c '.data')
r2=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":2},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -c '.data')
if [[ "$r1" != "$r2" ]]; then
    echo "  ✅ PASS (different seeds -> different data)"
    PASS=$((PASS + 1))
else
    echo "  ❌ FAIL: Seeds 1 and 2 produced identical data"
    FAIL=$((FAIL + 1))
fi

# Test 20: Verifies that the same seed deterministically returns identical data
echo ""
echo "▸ Deterministic reproducibility check: Same seed -> same data"
r1=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -c '.data')
r2=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -c '.data')
if [[ "$r1" == "$r2" ]]; then
    echo "  ✅ PASS (same seed -> same data)"
    PASS=$((PASS + 1))
else
    echo "  ❌ FAIL: Same seed produced different data"
    FAIL=$((FAIL + 1))
fi

# ──────────── Performance Tests ────────────

# Test 21: Performance — Medium grid (256×256)
# Verifies if a 256×256 grid can be generated within acceptable time limits (< 10s)
echo ""
echo "▸ Performance test: Medium grid 256×256"
start=$(date +%s%N)
response=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[256,256]}}')
end=$(date +%s%N)
elapsed_ms=$(( (end - start) / 1000000 ))
data_rows=$(echo "$response" | jq '.data | length')
data_cols=$(echo "$response" | jq '.data[0] | length')
if [[ "$data_rows" -eq 256 && "$data_cols" -eq 256 && "$elapsed_ms" -lt 10000 ]]; then
    echo "  ✅ PASS (${data_rows}×${data_cols} in ${elapsed_ms}ms)"
    PASS=$((PASS + 1))
else
    echo "  ❌ FAIL: 256×256 grid — data=${data_rows}×${data_cols}, time=${elapsed_ms}ms"
    FAIL=$((FAIL + 1))
fi

# Test 22: Performance — Large grid (512×512)
# Verifies if a 512×512 grid can be generated (~2 MB JSON payload, allowed up to 30s)
echo ""
echo "▸ Performance test: Large grid 512×512 (~2 MB JSON)"
start=$(date +%s%N)
response=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[512,512]}}')
end=$(date +%s%N)
elapsed_ms=$(( (end - start) / 1000000 ))
data_rows=$(echo "$response" | jq '.data | length')
data_cols=$(echo "$response" | jq '.data[0] | length')
if [[ "$data_rows" -eq 512 && "$data_cols" -eq 512 && "$elapsed_ms" -lt 30000 ]]; then
    echo "  ✅ PASS (${data_rows}×${data_cols} in ${elapsed_ms}ms)"
    PASS=$((PASS + 1))
else
    echo "  ❌ FAIL: 512×512 grid — data=${data_rows}×${data_cols}, time=${elapsed_ms}ms"
    FAIL=$((FAIL + 1))
fi

# ──────────── Summary ────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Test Summary"
echo "║  Total: $((PASS + FAIL))  |  ✅ Passed: $PASS  |  ❌ Failed: $FAIL"
echo "╚══════════════════════════════════════════════════════════════╝"
exit "$FAIL"