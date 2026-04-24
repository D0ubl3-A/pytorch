# Operator Benchmark Regression Validation Skill

This skill analyzes operator benchmark results to detect performance regressions and validate that code changes haven't negatively impacted performance.

## Overview

The regression validation system automatically analyzes benchmark results after they complete and posts findings to the PR.

## How It Works

```
Benchmark Job Completes (operator_benchmark.yml or operator_microbenchmark.yml)
    ↓
[claude-operator-benchmark-regression.yml] triggers via workflow_run
    ↓
Job 1: analyze-regression (READ-ONLY)
    ├─ Extract PR number from benchmark run
    ├─ Download benchmark result artifacts
    ├─ Load baseline data from CSV files or previous runs
    ├─ Compare performance metrics
    ├─ Apply regression thresholds
    └─ Produce /tmp/regression_analysis_output.json
    ↓
Job 2: post-results (WRITE)
    ├─ Parse regression analysis
    ├─ Format results as markdown comment
    ├─ Post comment to PR
    └─ Add labels (perf-regression, do-not-merge)
```

## Regression Detection

### Thresholds

| Change | Severity | Action |
|--------|----------|--------|
| >20% slower | Critical | Block merge |
| 10-20% slower | High | Require investigation |
| 5-10% slower | Medium | Approve with note |
| 2-5% slower | Low | Minor note |
| <2% change | - | Noise, ignore |
| Faster | Improvement | Celebrate! |

### Context-Aware Analysis

**Operator importance weighting:**
- Core operators (matmul, conv, linear): Lower tolerance (5%)
- Common operators (activations, norms): Standard tolerance (10%)
- Specialized operators: Higher tolerance (15%)

**Duration-based thresholds:**
- Micro-benchmarks (<100μs): 10% threshold (more noise)
- Mid-range (100μs-10ms): 5% threshold
- Macro-benchmarks (>10ms): 2% threshold (stable)

## Baseline Sources

Priority order for baseline data:

1. **Expected CSV files** (primary):
   - `benchmarks/operator_benchmark/x86_64_expected_ci_operator_benchmark_eager_float32_cpu.csv`
   - `benchmarks/operator_benchmark/aarch64_expected_ci_operator_benchmark_eager_float32_cpu.csv`

2. **Previous benchmark run** (fallback):
   - Results from PR base commit
   - Downloaded from previous workflow runs

3. **Historical average** (fallback):
   - Average of last 10 runs on main branch
   - From performance dashboard or S3

## Output Format

```json
{
  "pr_number": 12345,
  "overall_result": "regression_detected",
  "summary": {
    "total_operators_tested": 50,
    "regressions_detected": 2,
    "critical_regressions": 0,
    "high_regressions": 1,
    "medium_regressions": 1,
    "improvements_detected": 1
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
      "potential_cause": "Changes to CUDA kernels..."
    }
  ],
  "recommendation": "require_investigation"
}
```

## PR Comment Format

### Regression Detected

```markdown
## ⚠️ Performance Regression Detected

**Benchmark Run:** [View Results](...)

### Regressions Found

| Operator | Config | Severity | Change | Baseline | Current |
|----------|--------|----------|--------|----------|---------|
| torch.matmul | M=1024, N=1024, K=1024 (CUDA) | HIGH | +17.0% | 150.2μs | 175.8μs |

### Analysis

The regression in torch.matmul is concerning as it's a core operator...

### Recommendation

🛑 **Block merge until investigated**

---
🤖 *Automated analysis by Claude Code*
```

### No Regression

```markdown
## ✅ No Performance Regressions Detected

Benchmarks completed successfully with no significant performance degradation.

**Operators tested:** 50
**Improvements detected:** 1 (torch.relu: -15.9%)

---
🤖 *Automated analysis by Claude Code*
```

## Labels

Labels added based on findings:

| Recommendation | Labels Added |
|----------------|--------------|
| `block_merge` | `perf-regression`, `do-not-merge` |
| `require_investigation` | `perf-regression` |
| `approve_with_note` | (none) |
| `approve` | (none) |

## Testing

### Manual Testing

Trigger regression analysis manually:

```bash
# Trigger for a specific PR and benchmark run
gh workflow run claude-operator-benchmark-regression.yml \
  -f pr_number=12345 \
  -f benchmark_run_id=9876543210
```

### Local Testing

Test the skill locally:

```bash
cd pytorch

# Create mock benchmark results
mkdir -p /tmp/benchmark-results
echo "operator,config,time_us" > /tmp/benchmark-results/results.csv
echo "torch.matmul,M=1024 N=1024 K=1024,175.8" >> /tmp/benchmark-results/results.csv

# Run skill
claude --skill operator-benchmark-regression <<EOF
Analyze benchmark results in /tmp/benchmark-results/
Compare against baselines in benchmarks/operator_benchmark/x86_64_expected_*.csv
For PR #12345
EOF
```

## Disabling

To disable regression analysis:

1. **Disable workflow:**
   ```bash
   gh workflow disable claude-operator-benchmark-regression.yml
   ```

2. **Or remove workflow file:**
   ```bash
   rm .github/workflows/claude-operator-benchmark-regression.yml
   ```

## Troubleshooting

### Analysis not triggering

**Check:**
1. Did the benchmark workflow complete successfully?
2. Is the repository `pytorch/pytorch`?
3. Is the workflow enabled?

**Debug:**
```bash
# List recent workflow runs
gh run list --workflow=claude-operator-benchmark-regression.yml --limit 5

# View specific run
gh run view RUN_ID --log
```

### Cannot determine PR number

**Symptoms:**
- `skip=true` in logs
- "Could not determine PR number" warning

**Fix:**
- For scheduled/non-PR benchmark runs, this is expected
- For PR runs, check that the benchmark workflow includes PR metadata

### Baseline data not found

**Symptoms:**
- `"baseline_source": "none"` in output
- `overall_result: "inconclusive"`

**Fix:**
1. Verify CSV files exist in `benchmarks/operator_benchmark/`
2. Check CSV file format matches expected schema
3. Fall back to historical data if available

### False positives (noise)

**Symptoms:**
- Small regressions flagged (<5%)
- Inconsistent results across runs

**Fix:**
1. Adjust thresholds in `SKILL.md`
2. Require multiple runs to confirm regression
3. Use larger tolerance for micro-benchmarks

## Configuration

Future: Configuration file at `.claude/operator-benchmark-regression-config.json`:

```json
{
  "thresholds": {
    "critical": 0.20,
    "high": 0.10,
    "medium": 0.05,
    "low": 0.02
  },
  "operator_weights": {
    "torch.matmul": "critical",
    "torch.conv2d": "critical",
    "torch.relu": "high"
  },
  "baseline_strategy": "csv_first|previous_run|historical_average",
  "noise_tolerance": 0.02,
  "require_multi_run_confirmation": false
}
```

## References

- **Skill definition:** `SKILL.md`
- **Output schema:** `regression_output_schema.json`
- **Workflow:** `.github/workflows/claude-operator-benchmark-regression.yml`
- **Benchmark workflows:**
  - `.github/workflows/operator_benchmark.yml`
  - `.github/workflows/operator_microbenchmark.yml`
- **Performance dashboard:** https://hud.pytorch.org/benchmark/v3/dashboard/pytorch_operator_microbenchmark
