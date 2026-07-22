# Bank manager one-behavior configs

One behavior per YAML — the ASSERT best practice. Each YAML isolates a single failure mode so the adversarial test-set is concentrated and the judge taxonomy stays tight.

## Layout

This folder contains 12 configs: 4 failure modes × 3 arms.

| Failure mode | Suite | Baseline unguarded | Defensive prompting | ACS control plane |
| --- | --- | --- | --- | --- |
| Financial distortion | `bank-1b-distortion` | `distortion-baseline.yaml` | `distortion-prompted.yaml` | `distortion-acs.yaml` |
| Sensitive-data leak | `bank-1b-data-leak` | `data-leak-baseline.yaml` | `data-leak-prompted.yaml` | `data-leak-acs.yaml` |
| Policy fabrication | `bank-1b-policy-fab` | `policy-fab-baseline.yaml` | `policy-fab-prompted.yaml` | `policy-fab-acs.yaml` |
| Unauthorized transaction | `bank-1b-unauth-txn` | `unauth-txn-baseline.yaml` | `unauth-txn-prompted.yaml` | `unauth-txn-acs.yaml` |

Each failure mode is its own suite. The 3 arms in that suite share the same generated test set, so baseline, prompted, and ACS runs are an apples-to-apples comparison. That is the 1 behavior = 1 suite pattern.

## Run all configs

Run `baseline` first for each suite. Baseline generates the suite-level `taxonomy.json` and `test_set.jsonl`; `prompted` and `acs` reuse them. Do not use a naive alphabetical `*.yaml` loop, because it can run `-acs` before `-baseline`.

From the repository root:

```powershell
$behaviorDir = ".\examples\bank_manager_agent_control\behaviors"

Get-ChildItem $behaviorDir -Filter "*-baseline.yaml" | Sort-Object Name | ForEach-Object {
    assert-ai run --config $_.FullName
}

Get-ChildItem $behaviorDir -Filter "*.yaml" |
    Where-Object { $_.Name -notlike "*-baseline.yaml" } |
    Sort-Object Name |
    ForEach-Object {
        assert-ai run --config $_.FullName
    }
```

If you need to overwrite an existing run, add `--override`.

## Compare results

Use the viewer compare view within one suite. Rows are behavior categories; columns are up to 4 runs, so each failure-mode suite can show the 3 arms side-by-side.

For the full 4-failure-mode × 3-arm grid across all 4 suites, use the companion results-matrix command:

```powershell
assert-ai results matrix `
    --suite bank-1b-distortion --suite bank-1b-data-leak `
    --suite bank-1b-policy-fab --suite bank-1b-unauth-txn `
    --metric policy_violation

assert-ai results matrix `
    --suite bank-1b-distortion --suite bank-1b-data-leak `
    --suite bank-1b-policy-fab --suite bank-1b-unauth-txn `
    --metric strict_overrefusal
```

If the companion CLI PR lands with positional run arguments instead, pass all 12 runs explicitly:

```powershell
assert-ai results matrix `
    bank-1b-distortion/baseline bank-1b-distortion/prompted bank-1b-distortion/acs `
    bank-1b-data-leak/baseline bank-1b-data-leak/prompted bank-1b-data-leak/acs `
    bank-1b-policy-fab/baseline bank-1b-policy-fab/prompted bank-1b-policy-fab/acs `
    bank-1b-unauth-txn/baseline bank-1b-unauth-txn/prompted bank-1b-unauth-txn/acs `
    --metric policy_violation
```

## Strict overrefusal

Because `policy_violation` and `overrefusal` are taxonomy-reserved, this demo disables the built-in `overrefusal` dimension and scores a custom rubric-driven `strict_overrefusal` dimension instead.
