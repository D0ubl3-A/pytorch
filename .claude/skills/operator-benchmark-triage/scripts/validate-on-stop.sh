#!/usr/bin/env bash
# Stop hook to validate that the output file was created and is valid JSON

set -euo pipefail

OUTPUT_FILE="/tmp/benchmark_analysis_output.json"

if [[ ! -f "$OUTPUT_FILE" ]]; then
    echo "ERROR: Output file not found at $OUTPUT_FILE" >&2
    echo "The analysis must produce a benchmark_analysis_output.json file" >&2
    exit 1
fi

# Validate JSON structure
if ! jq empty "$OUTPUT_FILE" 2>/dev/null; then
    echo "ERROR: Invalid JSON in output file" >&2
    exit 1
fi

# Validate required fields
REQUIRED_FIELDS=("pr_number" "analysis_timestamp" "regression_risk" "benchmark_scope" "devices" "priority_level" "rationale")

for field in "${REQUIRED_FIELDS[@]}"; do
    if ! jq -e ".$field" "$OUTPUT_FILE" >/dev/null 2>&1; then
        echo "ERROR: Missing required field: $field" >&2
        exit 1
    fi
done

echo "✓ Output file validated successfully" >&2
exit 0
