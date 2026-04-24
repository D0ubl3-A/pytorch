#!/usr/bin/env python3
"""
Post-hook script to format regression analysis output.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def format_output():
    """Format and validate the regression analysis output."""
    output_file = Path("/tmp/regression_analysis_output.json")

    if not output_file.exists():
        print("No regression analysis output found", file=sys.stderr)
        return

    try:
        with open(output_file) as f:
            output = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in output file: {e}", file=sys.stderr)
        sys.exit(1)

    # Add timestamp if missing
    if "analysis_timestamp" not in output:
        output["analysis_timestamp"] = datetime.utcnow().isoformat() + "Z"

    # Ensure summary counts are consistent
    if "regressions" in output:
        severity_counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0
        }
        for reg in output["regressions"]:
            severity = reg.get("severity", "medium")
            severity_counts[severity] += 1

        if "summary" not in output:
            output["summary"] = {}

        output["summary"]["critical_regressions"] = severity_counts["critical"]
        output["summary"]["high_regressions"] = severity_counts["high"]
        output["summary"]["medium_regressions"] = severity_counts["medium"]
        output["summary"]["low_regressions"] = severity_counts["low"]
        output["summary"]["regressions_detected"] = len(output["regressions"])

    if "improvements" in output:
        if "summary" not in output:
            output["summary"] = {}
        output["summary"]["improvements_detected"] = len(output["improvements"])

    # Write back
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print("✓ Regression analysis output formatted successfully", file=sys.stderr)


if __name__ == "__main__":
    format_output()
