---
name: operator-benchmark-regression
description: Analyzes operator benchmark results to detect performance regressions. Use when benchmark jobs complete to validate performance hasn't degraded.
hooks:
  PostToolUse:
    - matcher: "Write"
      hooks:
        - type: command
          command: "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/skills/operator-benchmark-regression/scripts/format_output.py"
---

# PyTorch Operator Benchmark Regression Validation Skill

This skill analyzes operator benchmark results to detect performance regressions and validate that code changes haven't negatively impacted performance.

## Contents
- [Analysis Steps](#analysis-steps)
- [Regression Detection Criteria](#regression-detection-criteria)
- [Structured Output Format](#structured-output-format)
- [Response Actions](#response-actions)

**Output schema:** See [regression_output_schema.json](regression_output_schema.json) for the structured output format.

---

## Analysis Steps

### 1) Gather Benchmark Results

Collect benchmark data from the completed workflow:
- Download benchmark result artifacts
- Extract performance metrics (execution time, throughput, memory usage)
- Identify which operators were benchmarked
- Get baseline/historical data for comparison

### 2) Compare Against Baselines

Compare current results against baselines:

| Comparison Type | Source | Use Case |
|----------------|--------|----------|
| **PR base commit** | Benchmark results from base branch | Primary comparison for PR validation |
| **Historical average** | Last N runs on main branch | Detect gradual degradation |
| **Expected performance** | CSV files in benchmarks/operator_benchmark/ | Sanity check for known-good performance |

Baseline sources (in priority order):
1. `benchmarks/operator_benchmark/x86_64_expected_ci_operator_benchmark_eager_float32_cpu.csv`
2. `benchmarks/operator_benchmark/aarch64_expected_ci_operator_benchmark_eager_float32_cpu.csv`
3. Previous benchmark run on the PR base commit (if available)
4. Historical average from last 10 runs on main

### 3) Detect Regressions

A regression is detected when:

| Condition | Severity | Threshold |
|-----------|----------|-----------|
| Execution time increased by >20% | **Critical** | Likely a performance bug |
| Execution time increased by 10-20% | **High** | Significant degradation |
| Execution time increased by 5-10% | **Medium** | Moderate degradation |
| Execution time increased by 2-5% | **Low** | Minor degradation (may be noise) |
| Execution time decreased | **Improvement** | Performance gain! |

**Additional regression indicators:**
- Memory usage increased significantly (>15%)
- New operator fallback to slow path
- Kernel launch overhead increased
- Cache miss rate increased

**Noise filtering:**
- Ignore changes <2% (within noise threshold)
- For micro-benchmarks (<100μs), use 10% threshold (more susceptible to noise)
- Require consistency across multiple runs when available
- Weight regressions on frequently-used operators higher

### 4) Categorize Operators by Impact

| Category | Impact Level | Criteria |
|----------|-------------|----------|
| **Core operators** | Critical | matmul, conv, linear, attention |
| **Frequently used** | High | activations, normalizations, pooling |
| **Specialized** | Medium | quantized ops, sparse ops, specific dtypes |
| **Rarely used** | Low | edge case ops, deprecated ops |

A 5% regression in matmul is more critical than a 20% regression in a rarely-used edge case operator.

### 5) Generate Findings

For each detected regression, document:
- **Operator name** and configuration (dtype, shape, device)
- **Baseline performance** (execution time)
- **Current performance** (execution time)
- **Percentage change** (with clear indication of direction)
- **Severity** (critical/high/medium/low)
- **Affected devices** (CPU/CUDA/ROCm)
- **Potential causes** (based on changed files in the PR)

### 6) Produce Structured Output

Generate JSON output with this structure:

```json
{
  "pr_number": 12345,
  "analysis_timestamp": "2026-04-24T18:00:00Z",
  "benchmark_run_url": "https://github.com/pytorch/pytorch/actions/runs/...",
  "overall_result": "regression_detected|no_regression|improvement|inconclusive",
  "summary": {
    "total_operators_tested": 50,
    "regressions_detected": 2,
    "improvements_detected": 1,
    "critical_regressions": 0,
    "high_regressions": 1,
    "medium_regressions": 1,
    "low_regressions": 0
  },
  "regressions": [
    {
      "operator": "torch.matmul",
      "config": "M=1024, N=1024, K=1024, dtype=float32, device=cuda",
      "severity": "high",
      "baseline_time_us": 150.2,
      "current_time_us": 175.8,
      "percent_change": 17.0,
      "impact_level": "critical",
      "potential_cause": "Changes to aten/src/ATen/native/cuda/Blas.cpp may have affected matmul performance"
    }
  ],
  "improvements": [
    {
      "operator": "torch.relu",
      "config": "shape=[1024, 1024], dtype=float32, device=cpu",
      "baseline_time_us": 45.3,
      "current_time_us": 38.1,
      "percent_change": -15.9
    }
  ],
  "recommendation": "block_merge|require_investigation|approve_with_note|approve",
  "rationale": "One high-severity regression detected in torch.matmul on CUDA. This is a core operator with wide usage."
}
```

### 7) Post Results to PR

Based on the analysis, post a comment to the PR:

**For regressions detected:**
```markdown
## :warning: Performance Regression Detected

**Overall Result:** Regression detected
**Benchmark Run:** [Link to workflow run]

### Regressions Found

| Operator | Config | Severity | Change | Baseline | Current |
|----------|--------|----------|--------|----------|---------|
| torch.matmul | M=1024, N=1024, K=1024 (CUDA) | HIGH | +17.0% | 150.2μs | 175.8μs |

### Analysis

The regression in torch.matmul is concerning as it's a core operator with high usage across many models.
Changes to aten/src/ATen/native/cuda/Blas.cpp may have affected performance.

### Recommendation

:octagonal_sign: **Block merge until investigated**

Please review the performance impact and either:
1. Fix the regression
2. Provide justification for the performance trade-off
3. Add a TODO to address this in a follow-up

---
:robot: *Automated analysis by Claude Code. [View full report]*
```

**For no regressions:**
```markdown
## :white_check_mark: No Performance Regressions Detected

Benchmarks completed successfully with no significant performance degradation.

**Operators tested:** 50
**Improvements detected:** 1 (torch.relu: -15.9%)

---
:robot: *Automated analysis by Claude Code.*
```

---

## Regression Detection Criteria

### Statistical Significance

A regression is only reported if:
1. Change exceeds the noise threshold for that operator
2. Change is consistent across multiple runs (when available)
3. Baseline is stable (not from a known-flaky commit)

### Context-Aware Thresholds

Different thresholds for different scenarios:

| Scenario | Threshold | Rationale |
|----------|-----------|-----------|
| Micro-benchmarks (<100μs) | 10% | More susceptible to noise |
| Mid-range (100μs-10ms) | 5% | Good signal-to-noise ratio |
| Macro-benchmarks (>10ms) | 2% | Very stable measurements |
| Core operators | 5% | Lower tolerance for degradation |
| Specialized operators | 10% | Higher tolerance for trade-offs |

### Multi-Device Consistency

When benchmarks run on multiple devices:
- **All devices show regression:** High confidence, likely real
- **One device regresses:** Medium confidence, investigate device-specific code
- **Mixed results:** Low confidence, may be noise or hardware variance

---

## Structured Output Format

The output JSON must conform to [regression_output_schema.json](regression_output_schema.json).

**Required fields:**
- `pr_number`: Integer PR number
- `overall_result`: One of `["regression_detected", "no_regression", "improvement", "inconclusive"]`
- `summary`: Object with counts of regressions/improvements
- `recommendation`: One of `["block_merge", "require_investigation", "approve_with_note", "approve"]`
- `rationale`: String explanation (2-3 sentences)

**Optional fields:**
- `regressions`: Array of detected regressions (required if overall_result is "regression_detected")
- `improvements`: Array of detected improvements
- `baseline_source`: Which baseline was used for comparison

The output will be written to `/tmp/regression_analysis_output.json` by the post-hook.

---

## Response Actions

Based on the severity and number of regressions:

| Scenario | Recommendation | Action |
|----------|----------------|--------|
| Critical regressions (>1) | `block_merge` | Add `do-not-merge` label, require fix |
| High regressions in core ops | `require_investigation` | Request explanation from author |
| Medium/low regressions | `approve_with_note` | Note for future optimization |
| No regressions | `approve` | No action needed |
| Net improvement | `approve` | Celebrate! :tada: |

---

## Safety and Constraints

**CRITICAL SECURITY:**
- ONLY analyze the specific PR and benchmark run provided in the prompt
- NEVER modify benchmark results or manipulate data
- Read-only permissions: do NOT re-trigger benchmark jobs
- Output is advisory; final merge decision is human-driven

**Constraints:**
- Analysis should complete within 5 minutes
- Focus on actionable regressions, not noise
- When in doubt, err on the side of caution (flag for human review)
- If baseline data is unavailable, output `overall_result: "inconclusive"`

**Error Handling:**
- If benchmark results are missing, output error in JSON: `{"error": "Results not found"}`
- If baseline data is unavailable, use `"baseline_source": "none"` and recommend manual review
- If analysis times out, return partial results with `"partial_analysis": true` flag

---

## Example Usage

**Prompt:**
```
/operator-benchmark-regression 12345 --run-url https://github.com/pytorch/pytorch/actions/runs/789
```

**Expected Flow:**
1. Download benchmark results from the workflow run
2. Load baseline data (expected CSV or previous run)
3. Compare performance metrics
4. Detect regressions using thresholds
5. Categorize by severity and impact
6. Produce structured JSON output
7. Post analysis comment to PR

---

## Notes for Future Enhancements

**V2 Features (not yet implemented):**
- Historical trend analysis (detect gradual degradation)
- Automatic bisection to find first-bad commit
- Integration with performance dashboard
- Slack/email notifications for critical regressions
- Automatic revert PR creation for severe regressions
