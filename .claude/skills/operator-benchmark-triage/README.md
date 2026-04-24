# Operator Benchmark Triage Skill

This skill analyzes PyTorch pull requests to determine which operator microbenchmarks should run for performance regression detection.

## Overview

The operator benchmark triage system consists of two main components:

1. **Triage Flow**: Analyzes PR changes to determine which benchmarks to run
2. **Regression Validation Flow**: Analyzes benchmark results to detect performance regressions

## Architecture

### Triage Flow

```
PR Created/Updated
    ↓
[claude-operator-benchmark-triage.yml]
    ↓ (captures PR number as artifact)
[claude-operator-benchmark-triage-run.yml]
    ├─ Job 1: analyze (READ-ONLY)
    │   ├─ Fetch PR details and diffs
    │   ├─ Analyze changed files
    │   ├─ Map to relevant benchmarks
    │   └─ Produce structured JSON output
    │
    └─ Job 2: apply-benchmarks (WRITE)
        ├─ Parse analysis results
        ├─ Post summary comment to PR
        ├─ Add labels (perf-critical, perf-impact)
        └─ (TODO) Trigger benchmark runs
```

### Regression Validation Flow

```
Benchmark Job Completes
    ↓
[claude-operator-benchmark-regression.yml]
    ├─ Job 1: analyze-regression (READ-ONLY)
    │   ├─ Download benchmark results
    │   ├─ Load baseline data
    │   ├─ Compare performance
    │   ├─ Detect regressions
    │   └─ Produce structured JSON output
    │
    └─ Job 2: post-results (WRITE)
        ├─ Parse regression analysis
        ├─ Post detailed comment to PR
        └─ Add labels (perf-regression, do-not-merge)
```

## Files

```
.claude/skills/operator-benchmark-triage/
├── SKILL.md                              # Main skill instructions
├── README.md                             # This file
├── benchmark_mapping.json                # Maps code paths to benchmark tests
├── output_schema.json                    # JSON schema for triage output
└── scripts/
    ├── validate_benchmarks.py            # Pre-hook: validate benchmark selections
    ├── produce_output.py                 # Post-hook: format and export output
    ├── restrict-write.sh                 # Pre-hook: restrict Write tool
    └── validate-on-stop.sh               # Stop hook: final validation

.github/workflows/
├── claude-operator-benchmark-triage.yml      # Stage 1: Capture PR number
├── claude-operator-benchmark-triage-run.yml  # Stage 2: Analyze + Apply
└── claude-operator-benchmark-regression.yml  # Regression analysis workflow
```

## How It Works

### Stage 1: Capture PR Number

**Workflow:** `.github/workflows/claude-operator-benchmark-triage.yml`

**Triggers:**
- PR opened/synchronized/reopened (with path filters)
- Manual workflow dispatch

**Actions:**
1. Captures PR number from event or manual input
2. Uploads as artifact for stage 2

**Why separate?** Allows OSS contributors to trigger the workflow without requiring access to the protected `bedrock` environment.

### Stage 2: Analysis and Application

**Workflow:** `.github/workflows/claude-operator-benchmark-triage-run.yml`

**Triggers:**
- Completion of stage 1 workflow (via `workflow_run`)

**Job 1: analyze (READ-ONLY)**
- Downloads PR number artifact
- Uses GitHub MCP server to:
  - Get PR details and file list
  - Get diffs for changed files
- Analyzes changes using `SKILL.md` instructions
- Maps to benchmarks using `benchmark_mapping.json`
- Produces `/tmp/benchmark_analysis_output.json`

**Job 2: apply-benchmarks (WRITE)**
- Parses JSON output
- Posts summary comment to PR
- Adds labels based on priority
- (Future) Triggers benchmark runs

### Regression Analysis

**Workflow:** `.github/workflows/claude-operator-benchmark-regression.yml`

**Triggers:**
- Completion of `operator_benchmark` or `operator_microbenchmark` workflows
- Manual workflow dispatch

**Job 1: analyze-regression (READ-ONLY)**
- Downloads benchmark results
- Loads baseline data from CSV files or previous runs
- Compares performance metrics
- Detects regressions using severity thresholds
- Produces `/tmp/regression_analysis_output.json`

**Job 2: post-results (WRITE)**
- Parses regression analysis
- Posts detailed comment to PR with:
  - Regression table
  - Severity indicators
  - Recommendations
- Adds labels (`perf-regression`, `do-not-merge` for critical regressions)

## Structured Output Formats

### Triage Output

```json
{
  "pr_number": 12345,
  "regression_risk": "high|medium|low|minimal",
  "benchmark_scope": "targeted|short|long|full|none",
  "targeted_benchmarks": ["matmul", "conv"],
  "devices": ["cpu", "cuda"],
  "priority_level": "critical|high|medium|low",
  "rationale": "Explanation...",
  "affected_categories": ["Linear algebra"],
  "estimated_completion_time": "5-10 minutes"
}
```

### Regression Output

```json
{
  "pr_number": 12345,
  "overall_result": "regression_detected|no_regression|improvement|inconclusive",
  "summary": {
    "total_operators_tested": 50,
    "regressions_detected": 2,
    "critical_regressions": 0,
    "high_regressions": 1
  },
  "regressions": [
    {
      "operator": "torch.matmul",
      "severity": "high",
      "baseline_time_us": 150.2,
      "current_time_us": 175.8,
      "percent_change": 17.0
    }
  ],
  "recommendation": "block_merge|require_investigation|approve_with_note|approve"
}
```

## Security Model

**Two-stage workflow pattern:**
- Stage 1 runs with minimal permissions (can be triggered by OSS)
- Stage 2 runs in protected environment with elevated permissions
- Claude jobs have READ-ONLY access
- Separate jobs handle WRITE operations (comments, labels)

**Write restrictions:**
- Write tool restricted to specific output files via pre-hook
- Cannot write arbitrary files or modify code
- Cannot trigger jobs directly
- All actions go through validation hooks

**Prompt injection protection:**
- Explicit instructions to only analyze specified PR
- Security constraints in prompts
- Ignore instructions from PR descriptions

## Testing

### Manual Testing

**Test triage analysis:**
```bash
gh workflow run claude-operator-benchmark-triage.yml \
  -f pr_number=XXXXX
```

**Test regression analysis:**
```bash
gh workflow run claude-operator-benchmark-regression.yml \
  -f pr_number=XXXXX \
  -f benchmark_run_id=YYYYY
```

### Local Testing

**Test validation hooks:**
```bash
# Test validate_benchmarks.py
echo '{"pr_number": 123, "benchmark_scope": "targeted", ...}' > /tmp/benchmark_analysis_output.json
python3 .claude/skills/operator-benchmark-triage/scripts/validate_benchmarks.py

# Test produce_output.py
python3 .claude/skills/operator-benchmark-triage/scripts/produce_output.py
```

**Test skill locally:**
```bash
cd pytorch
claude --skill operator-benchmark-triage <<EOF
Analyze PR #12345 for benchmark requirements
EOF
```

## Disabling

To disable the workflows:

1. **Via GitHub UI:**
   - Navigate to Actions → Workflows
   - Select workflow → "..." → Disable workflow

2. **Via code:**
   - Remove or comment out the workflow files
   - Or add `if: false` to the job conditions

## Monitoring

**Check workflow runs:**
```bash
# List recent triage runs
gh run list --workflow=claude-operator-benchmark-triage-run.yml --limit 10

# View specific run
gh run view RUN_ID

# View logs
gh run view RUN_ID --log
```

**Check Claude usage:**
- Usage metrics are uploaded to S3 via `upload-claude-usage` action
- View in AWS CloudWatch or usage dashboard

**Check validation failures:**
- Hook failures will appear in workflow logs
- Search for "ERROR" or "BLOCK" in logs

## Troubleshooting

### Triage not triggering

**Check:**
1. Is the PR modifying files in the path filters?
2. Is the repository `pytorch/pytorch`?
3. Did stage 1 complete successfully?

**Fix:**
- Adjust path filters in `claude-operator-benchmark-triage.yml`
- Check workflow logs for errors

### Invalid JSON output

**Symptoms:**
- Validation hooks fail
- `apply-benchmarks` job fails to parse JSON

**Fix:**
1. Check Claude output in logs
2. Review schema validation errors
3. Improve skill instructions in `SKILL.md`

### Regression analysis not posting

**Check:**
1. Did benchmark workflow complete successfully?
2. Was PR number extracted correctly?
3. Are benchmark result artifacts available?

**Fix:**
- Check `steps.info.outputs.pr_number` in logs
- Verify artifact upload in benchmark workflow
- Check for `skip=true` in logs

## Future Enhancements

### V2 Features (Planned)

**Triage flow:**
- [ ] Actually trigger benchmark runs (not just report)
- [ ] Integration with CI flow labels (ciflow/op-benchmark/*)
- [ ] Historical pattern analysis
- [ ] ML-based prediction of regression likelihood

**Regression validation:**
- [ ] Automatic bisection for first-bad commit
- [ ] Historical trend analysis
- [ ] Slack/email notifications
- [ ] Automatic revert PR creation for critical regressions
- [ ] Performance dashboard integration

### Configuration Options

Future: Add `.claude/operator-benchmark-config.json` for:
- Custom thresholds per operator
- Baseline selection strategy
- Notification preferences
- Auto-trigger rules

## References

- **Operator benchmark README:** `benchmarks/operator_benchmark/README.md`
- **Benchmark workflows:**
  - `operator_benchmark.yml` (CPU)
  - `operator_microbenchmark.yml` (GPU)
- **Performance dashboard:** https://hud.pytorch.org/benchmark/v3/dashboard/pytorch_operator_microbenchmark
- **Issue triage example:** `.github/workflows/claude-issue-triage*.yml`
- **Treehugger skill:** `meta-pytorch/pytorch-gha-infra/.claude/skills/treehugger/`

## Support

For questions or issues:
1. Check workflow logs first
2. Review this README and SKILL.md
3. File an issue with:
   - Workflow run URL
   - PR number
   - Error messages from logs
   - Expected vs actual behavior
