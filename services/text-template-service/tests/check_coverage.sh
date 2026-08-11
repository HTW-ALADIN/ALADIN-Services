#!/usr/bin/env sh
set -eu

report="${COVERAGE_REPORT:-coverage.lcov}"

# Exclude executable wiring and Clap's generated argument-declaration spans;
# CLI behavior is covered by tests/cli_contract.rs.
cargo llvm-cov \
  --locked \
  --all-features \
  --workspace \
  --ignore-filename-regex 'src/(main|cli_args).rs' \
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
