#!/usr/bin/env sh
set -eu

report="${COVERAGE_REPORT:-coverage.lcov}"

cargo llvm-cov \
  --locked \
  --all-features \
  --workspace \
  --ignore-filename-regex 'src/main.rs' \
  --lcov \
  --output-path "$report"

awk -F '[:,]' '
  /^DA:/ {
    total += 1
    if ($3 > 0) {
      covered += 1
    }
  }
  END {
    if (total == 0) {
      print "coverage check failed: no executable library lines were reported" > "/dev/stderr"
      exit 1
    }
    printf "library line coverage: %d/%d (%.2f%%)\n", covered, total, 100 * covered / total
    if (covered != total) {
      exit 1
    }
  }
' "$report"
