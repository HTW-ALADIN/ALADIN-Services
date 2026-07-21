#!/bin/bash

BASE_URL="http://localhost:8000"
echo "Testing all 14 noise algorithms..."

# Test 1: Perlin (fastnoise_lite)
echo "1. Testing Perlin (fastnoise_lite)..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"perlin","backend":"fastnoise_lite","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 2: Perlin (noise_rs) 
echo "2. Testing Perlin (noise_rs)..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"perlin","backend":"noise_rs","params":{"seed":42},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 3: Simplex
echo "3. Testing Simplex..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"simplex","params":{"seed":123},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 4: OpenSimplex2 (fastnoise_lite)
echo "4. Testing OpenSimplex2 (fastnoise_lite)..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"opensimplex2","backend":"fastnoise_lite","params":{"seed":456},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 5: OpenSimplex2 (noise_rs)
echo "5. Testing OpenSimplex2 (noise_rs)..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"opensimplex2","backend":"noise_rs","params":{"seed":456},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 6: SuperSimplex
echo "6. Testing SuperSimplex..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"supersimplex","params":{"seed":789},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 7: Value noise
echo "7. Testing Value noise..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"value","params":{"seed":111},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 8: Cellular/Worley
echo "8. Testing Cellular..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"cellular","params":{"seed":222},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 9: FBM (Fractal Brownian Motion)
echo "9. Testing FBM..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"fbm","params":{"seed":333,"octaves":4,"frequency":0.1,"lacunarity":2.0,"persistence":0.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 10: Billow
echo "10. Testing Billow..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"billow","params":{"seed":444,"octaves":3},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 11: Ridged Multi
echo "11. Testing RidgedMulti..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"ridged_multi","params":{"seed":555,"octaves":4},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 12: Hybrid Multi
echo "12. Testing HybridMulti..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"hybrid_multi","params":{"seed":666,"octaves":4},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 13: PingPong
echo "13. Testing PingPong..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"pingpong","params":{"seed":777,"strength":2.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 14: Domain Warp
echo "14. Testing Domain Warp..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"domain_warp","params":{"seed":888,"amplitude":1.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 15: Combinator (Add)
echo "15. Testing Combinator (Add)..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"combinator","params":{"seed":999,"op":"add"},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 16: Utility (Constant)
echo "16. Testing Utility (Constant)..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"utility","params":{"kind":"constant","value":0.5},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

# Test 17: White Noise
echo "17. Testing White Noise..."
curl -s -X POST $BASE_URL/v1/noise \
  -H "Content-Type: application/json" \
  -d '{"algorithm":"white","params":{"seed":1010},"sampling":{"mode":"2d","dimensions":2,"size":[4,4]}}' | jq -r '.algorithm'

echo -e "\nAll algorithm tests completed!"