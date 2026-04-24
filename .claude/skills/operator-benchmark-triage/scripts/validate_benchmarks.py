#!/usr/bin/env python3
"""
Pre-hook validation script for operator benchmark triage.
Validates that benchmark selections are valid and reasonable.
"""

import json
import os
import sys
from pathlib import Path

# Exit codes
EXIT_ALLOW = 0  # Allow the tool call
EXIT_BLOCK = 1  # Block the tool call


def load_benchmark_mapping():
    """Load the benchmark mapping configuration."""
    script_dir = Path(__file__).parent
    mapping_file = script_dir.parent / "benchmark_mapping.json"

    if not mapping_file.exists():
        print(f"Warning: benchmark_mapping.json not found at {mapping_file}", file=sys.stderr)
        return {}

    with open(mapping_file) as f:
        return json.load(f)


def validate_benchmark_names(benchmarks, mapping):
    """Validate that benchmark names are valid."""
    if not benchmarks:
        return True

    # Extract all valid benchmark names from mapping
    valid_benchmarks = set()
    for category in mapping.get("categories", {}).values():
        valid_benchmarks.update(category.get("benchmarks", []))

    # Allow benchmark names without .py extension
    normalized_benchmarks = [
        b if b.endswith(".py") else f"{b}.py"
        for b in benchmarks
    ]

    invalid = [b for b in normalized_benchmarks if b not in valid_benchmarks]

    if invalid:
        print(f"ERROR: Invalid benchmark names: {invalid}", file=sys.stderr)
        print(f"Valid benchmarks are defined in benchmark_mapping.json", file=sys.stderr)
        return False

    return True


def validate_scope_and_benchmarks(scope, benchmarks):
    """Validate that scope and benchmarks are consistent."""
    if scope == "targeted" and not benchmarks:
        print("ERROR: benchmark_scope is 'targeted' but targeted_benchmarks is empty", file=sys.stderr)
        return False

    if scope == "none" and benchmarks:
        print("WARNING: benchmark_scope is 'none' but targeted_benchmarks is specified", file=sys.stderr)

    return True


def main():
    """
    Validate benchmark triage output before it's written.

    This hook is called before any tool use that might write benchmark output.
    It validates the structured output to ensure it's well-formed and reasonable.
    """

    # Check if there's output to validate
    output_file = Path("/tmp/benchmark_analysis_output.json")
    if not output_file.exists():
        # No output yet, allow the tool call
        sys.exit(EXIT_ALLOW)

    try:
        with open(output_file) as f:
            output = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in output file: {e}", file=sys.stderr)
        sys.exit(EXIT_BLOCK)

    # Load benchmark mapping
    mapping = load_benchmark_mapping()

    # Validate required fields
    required_fields = [
        "pr_number", "regression_risk", "benchmark_scope",
        "devices", "priority_level", "rationale"
    ]

    missing = [f for f in required_fields if f not in output]
    if missing:
        print(f"ERROR: Missing required fields: {missing}", file=sys.stderr)
        sys.exit(EXIT_BLOCK)

    # Validate enum fields
    valid_risks = ["high", "medium", "low", "minimal"]
    if output["regression_risk"] not in valid_risks:
        print(f"ERROR: Invalid regression_risk: {output['regression_risk']}", file=sys.stderr)
        sys.exit(EXIT_BLOCK)

    valid_scopes = ["targeted", "short", "long", "full", "none"]
    if output["benchmark_scope"] not in valid_scopes:
        print(f"ERROR: Invalid benchmark_scope: {output['benchmark_scope']}", file=sys.stderr)
        sys.exit(EXIT_BLOCK)

    valid_devices = ["cpu", "cuda", "rocm"]
    invalid_devices = [d for d in output["devices"] if d not in valid_devices]
    if invalid_devices:
        print(f"ERROR: Invalid devices: {invalid_devices}", file=sys.stderr)
        sys.exit(EXIT_BLOCK)

    # Validate benchmark names
    targeted_benchmarks = output.get("targeted_benchmarks", [])
    if not validate_benchmark_names(targeted_benchmarks, mapping):
        sys.exit(EXIT_BLOCK)

    # Validate consistency between scope and benchmarks
    if not validate_scope_and_benchmarks(output["benchmark_scope"], targeted_benchmarks):
        sys.exit(EXIT_BLOCK)

    # All validations passed
    print("✓ Benchmark triage output validated successfully", file=sys.stderr)
    sys.exit(EXIT_ALLOW)


if __name__ == "__main__":
    main()
