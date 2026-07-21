#!/bin/bash
# =============================================================================
# Smoke Tests for the Noise Generation Service
#
# Every test calls POST /v1/noise and validates the full JSON response,
# which now includes: id, status, algorithm, data (full grid), and size.
# There are no separate GET endpoints anymore.
# =============================================================================

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0

check_response() {
    local test_name="$1"
    local response="$2"
    local expected_alg="$3"

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

    # Check HTTP error (e.g. connection refused)
    if echo "$response" | jq -e . >/dev/null 2>&1; then
        if check_response "$test_name" "$response" "$expected_alg"; then
            ((PASS++))
        else
            echo "  Response: $(echo "$response" | jq -c '{id, algorithm, status, size}')"
            ((FAIL++))
        fi
    else
        echo "  ❌ FAIL: not valid JSON — is the server running?"
        echo "  Response: $response"
        ((FAIL++))
    fi
}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Noise Generation Service — Full Smoke Test Suite           ║"
echo "║  Target: $BASE_URL"
echo "╚══════════════════════════════════════════════════════════════╝"

# ──────────── Core Noise Algorithms ────────────

# Test 1: Perlin (fastnoise_lite backend)
# Prüft: Grundlegende Perlin-Noise-Erzeugung mit dem Standard-Backend
run_test \
    "Perlin (fastnoise_lite)" \
    "perlin" \
    '{"algorithm":"perlin","backend":"fastnoise_lite","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 2: Perlin (noise_rs backend)
# Prüft: Perlin-Noise mit alternativem Backend → gleicher Algorithmus, andere Implementierung
run_test \
    "Perlin (noise_rs)" \
    "perlin" \
    '{"algorithm":"perlin","backend":"noise_rs","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 3: Simplex (noise_rs only)
# Prüft: Simplex-Noise — verbesserte Rauschqualität bei geringerer Komplexität
run_test \
    "Simplex (noise_rs)" \
    "simplex" \
    '{"algorithm":"simplex","params":{"seed":123},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 4: OpenSimplex2 (fastnoise_lite)
# Prüft: Modernere Variante mit besserer visueller Qualität
run_test \
    "OpenSimplex2 (fastnoise_lite)" \
    "opensimplex2" \
    '{"algorithm":"opensimplex2","backend":"fastnoise_lite","params":{"seed":456},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 5: OpenSimplex2 (noise_rs)
# Prüft: OpenSimplex2 mit alternativem Backend
run_test \
    "OpenSimplex2 (noise_rs)" \
    "opensimplex2" \
    '{"algorithm":"opensimplex2","backend":"noise_rs","params":{"seed":456},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 6: SuperSimplex (noise_rs only)
# Prüft: Höherdimensionale Rauschvariante
run_test \
    "SuperSimplex (noise_rs)" \
    "supersimplex" \
    '{"algorithm":"supersimplex","params":{"seed":789},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 7: Value noise (default backend)
# Prüft: Gitterbasiertes Value-Noise mit kubischer Interpolation
run_test \
    "Value (fastnoise_lite)" \
    "value" \
    '{"algorithm":"value","params":{"seed":111},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 8: Cellular / Worley (fastnoise_lite)
# Prüft: Zellbasierte Muster (Voronoi/Worley) — Default-Parameter
run_test \
    "Cellular (fastnoise_lite)" \
    "cellular" \
    '{"algorithm":"cellular","params":{"seed":222},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# ──────────── Fractal Algorithms ────────────

# Test 9: FBM (Fractal Brownian Motion)
# Prüft: Mehr-oktaviges fraktales Rauschen mit Oktaven, Frequenz, Lückenhaftigkeit & Persistenz
run_test \
    "FBM (noise_rs)" \
    "fbm" \
    '{"algorithm":"fbm","params":{"seed":333,"octaves":4,"frequency":0.1,"lacunarity":2.0,"persistence":0.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 10: Billow (noise_rs only)
# Prüft: Billow-Rauschen (Absolutwert von Perlin) — erzeugt weiche, wellenartige Strukturen
run_test \
    "Billow (noise_rs)" \
    "billow" \
    '{"algorithm":"billow","params":{"seed":444,"octaves":3},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 11: Ridged Multi (fastnoise_lite)
# Prüft: Rückenartige fraktale Muster mit scharfen Graten
run_test \
    "RidgedMulti (fastnoise_lite)" \
    "ridged_multi" \
    '{"algorithm":"ridged_multi","params":{"seed":555,"octaves":4},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 12: Hybrid Multi (noise_rs only)
# Prüft: Hybrid-Multi-Fraktal-Rauschen — Kombination mehrerer Rauscharten
run_test \
    "HybridMulti (noise_rs)" \
    "hybrid_multi" \
    '{"algorithm":"hybrid_multi","params":{"seed":666,"octaves":4},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 13: PingPong (fastnoise_lite only)
# Prüft: PingPong-Fraktal mit Spiegelungseffekt, gesteuert über "strength"-Parameter
run_test \
    "PingPong (fastnoise_lite)" \
    "pingpong" \
    '{"algorithm":"pingpong","params":{"seed":777,"strength":2.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# ──────────── Advanced Algorithms ────────────

# Test 14: Domain Warp (fastnoise_lite only)
# Prüft: Domain-Warping — Koordinatentransformation für organische Verzerrungseffekte
run_test \
    "Domain Warp (fastnoise_lite)" \
    "domain_warp" \
    '{"algorithm":"domain_warp","params":{"seed":888,"amplitude":1.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 15: Combinator (Add)
# Prüft: Generische Kombinatoren — zwei Rauschquellen werden per "add" überlagert
run_test \
    "Combinator (Add)" \
    "combinator" \
    '{"algorithm":"combinator","params":{"seed":999,"op":"add"},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 16: Utility (Constant)
# Prüft: Deterministische Hilfsgeneratoren — konstanter Wert 0.5 im gesamten Feld
run_test \
    "Utility (Constant)" \
    "utility" \
    '{"algorithm":"utility","params":{"kind":"constant","value":0.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# Test 17: White Noise (native)
# Prüft: Native Weißes-Rauschen-Implementierung — rein zufällig, hash-basiert, kein Interpolationsgitter
run_test \
    "White Noise (native)" \
    "white" \
    '{"algorithm":"white","params":{"seed":1010},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}'

# ──────────── Response Validation Tests ────────────

# Test 18: Prüft, ob die Antworts das vollständige Datenraster enthält
echo ""
echo "▸ Response-Format-Prüfung: Vollständiges Datenraster (4×4)"
response=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":7},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}')
data_rows=$(echo "$response" | jq '.data | length')
data_cols=$(echo "$response" | jq '.data[0] | length')
size_field=$(echo "$response" | jq -c '.size')
if [[ "$data_rows" -eq 4 && "$data_cols" -eq 4 && "$size_field" == "[4,4]" ]]; then
    echo "  ✅ PASS (data=${data_rows}×${data_cols}, size=${size_field})"
    ((PASS++))
else
    echo "  ❌ FAIL: expected 4×4 grid, got data=${data_rows}×${data_cols}, size=${size_field}"
    ((FAIL++))
fi

# Test 19: Prüft, ob unterschiedliche Seeds unterschiedliche Daten erzeugen
echo ""
echo "▸ Deterministische Seed-Prüfung: Seed 1 ≠ Seed 2 (Perlin 4×4)"
r1=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":1},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -c '.data')
r2=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":2},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -c '.data')
if [[ "$r1" != "$r2" ]]; then
    echo "  ✅ PASS (unterschiedliche Seeds → unterschiedliche Daten)"
    ((PASS++))
else
    echo "  ❌ FAIL: Seeds 1 und 2 erzeugen identische Daten"
    ((FAIL++))
fi

# Test 20: Prüft, ob derselbe Seed deterministisch dieselben Daten liefert
echo ""
echo "▸ Deterministische Reproduzierbarkeit: Gleicher Seed → gleiche Daten"
r1=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -c '.data')
r2=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -c '.data')
if [[ "$r1" == "$r2" ]]; then
    echo "  ✅ PASS (gleicher Seed → gleiche Daten)"
    ((PASS++))
else
    echo "  ❌ FAIL: Gleicher Seed liefert unterschiedliche Daten"
    ((FAIL++))
fi

# ──────────── Performance Tests ────────────

# Test 21: Performance — Mittelgroßes Gitter (256×256)
# Prüft: Ob ein 256×256-Raster in akzeptabler Zeit generiert werden kann
echo ""
echo "▸ Performance-Test: Mittelgroßes Gitter 256×256"
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
    ((PASS++))
else
    echo "  ❌ FAIL: 256×256 grid — data=${data_rows}×${data_cols}, time=${elapsed_ms}ms"
    ((FAIL++))
fi

# Test 22: Performance — Großes Gitter (512×512)
# Prüft: Ob ein 512×512-Raster generiert werden kann (ca. 2 MB JSON-Payload)
echo ""
echo "▸ Performance-Test: Großes Gitter 512×512 (ca. 2 MB JSON)"
start=$(date +%s%N)
response=$(curl -s -X POST "$BASE_URL/v1/noise" \
    -H "Content-Type: application/json" \
    -d '{"algorithm":"perlin","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[512,512]}}')
end=$(date +%s%N)
elapsed_ms=$(( (end - start) / 1000000 ))
data_rows=$(echo "$response" | jq '.data | length')
data_cols=$(echo "$response" | jq '.data[0] | length')
# Für 512×512 erlauben wir bis zu 30 Sekunden
if [[ "$data_rows" -eq 512 && "$data_cols" -eq 512 && "$elapsed_ms" -lt 30000 ]]; then
    echo "  ✅ PASS (${data_rows}×${data_cols} in ${elapsed_ms}ms)"
    ((PASS++))
else
    echo "  ❌ FAIL: 512×512 grid — data=${data_rows}×${data_cols}, time=${elapsed_ms}ms"
    ((FAIL++))
fi

# ──────────── Summary ────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Test Summary"
echo "║  Total: $((PASS + FAIL))  |  ✅ Passed: $PASS  |  ❌ Failed: $FAIL"
echo "╚══════════════════════════════════════════════════════════════╝"
exit "$FAIL"