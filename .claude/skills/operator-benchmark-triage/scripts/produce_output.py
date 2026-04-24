#!/usr/bin/env python3
"""
Post-hook script to produce structured output from operator benchmark triage.
This script is called after Claude completes the analysis and formats the output
in a way that can be consumed by the benchmark trigger workflow.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def ensure_output_file():
    """Ensure the output file exists and has basic structure."""
    output_file = Path("/tmp/benchmark_analysis_output.json")

    if not output_file.exists():
        # Create a default output structure
        default_output = {
            "pr_number": int(os.environ.get("PR_NUMBER", 0)),
            "analysis_timestamp": datetime.utcnow().isoformat() + "Z",
            "regression_risk": "medium",
            "benchmark_scope": "short",
            "devices": ["cpu"],
            "priority_level": "medium",
            "rationale": "Default output - analysis may have been incomplete",
            "partial_analysis": True
        }

        with open(output_file, "w") as f:
            json.dump(default_output, f, indent=2)

        print(f"Created default output file at {output_file}", file=sys.stderr)

    return output_file


def add_metadata(output):
    """Add additional metadata to the output."""
    if "analysis_timestamp" not in output:
        output["analysis_timestamp"] = datetime.utcnow().isoformat() + "Z"

    # Add estimated completion time based on scope
    scope = output.get("benchmark_scope", "short")
    devices = output.get("devices", ["cpu"])

    time_estimates = {
        "none": "0 minutes",
        "targeted": f"{5 * len(devices)}-{10 * len(devices)} minutes",
        "short": f"{15 * len(devices)}-{30 * len(devices)} minutes",
        "long": f"{2 * len(devices)}-{4 * len(devices)} hours",
        "full": "8-12 hours"
    }

    output["estimated_completion_time"] = time_estimates.get(scope, "Unknown")

    # Generate CI tag for triggering benchmarks
    if scope != "none":
        pr_number = output.get("pr_number", "unknown")
        output["trigger_ci_tag"] = f"ciflow/op-benchmark/{pr_number}"

    return output


def main():
    """
    Post-process the benchmark triage output.

    This hook is called after Claude completes the analysis.
    It ensures the output file exists, adds metadata, and formats it
    for consumption by the benchmark trigger workflow.
    """

    # Ensure output file exists
    output_file = ensure_output_file()

    try:
        with open(output_file) as f:
            output = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in output file: {e}", file=sys.stderr)
        sys.exit(1)

    # Add metadata
    output = add_metadata(output)

    # Write back the updated output
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    # Also write to a GitHub Actions output file if in CI
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            # Write key outputs for GitHub Actions
            f.write(f"benchmark_scope={output.get('benchmark_scope', 'short')}\n")
            f.write(f"regression_risk={output.get('regression_risk', 'medium')}\n")
            f.write(f"priority_level={output.get('priority_level', 'medium')}\n")

            # Write targeted benchmarks as a comma-separated list
            if "targeted_benchmarks" in output:
                benchmarks = ",".join(output["targeted_benchmarks"])
                f.write(f"targeted_benchmarks={benchmarks}\n")

    print(f"✓ Benchmark triage output written to {output_file}", file=sys.stderr)
    print(f"  Scope: {output.get('benchmark_scope')}", file=sys.stderr)
    print(f"  Risk: {output.get('regression_risk')}", file=sys.stderr)
    print(f"  Devices: {', '.join(output.get('devices', []))}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
