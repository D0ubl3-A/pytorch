#!/usr/bin/env bash
# Pre-hook to restrict Write tool to only /tmp/benchmark_analysis_output.json

set -euo pipefail

# Get the file path from the Write tool call
# The hook receives tool use details via stdin in JSON format
FILE_PATH=$(jq -r '.file_path // empty' 2>/dev/null || echo "")

ALLOWED_FILE="/tmp/benchmark_analysis_output.json"

if [[ "$FILE_PATH" != "$ALLOWED_FILE" ]]; then
    echo "ERROR: Write tool is restricted to $ALLOWED_FILE only" >&2
    echo "Attempted to write to: $FILE_PATH" >&2
    exit 1
fi

# Allow the write
exit 0
