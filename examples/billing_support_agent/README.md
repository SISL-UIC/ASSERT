# Billing support agent — B2B billing chatbot governance

A B2B billing-support chatbot for authenticated customers: it looks up invoices
and account/PII, updates payment methods, changes plans, cancels subscriptions,
issues refunds within policy, and escalates to a human. Wrapped as an [ASSERT
callable target](../../docs/targets/callable.md) so the judge can inspect the tool
trace, not just the final answer.

The baseline agent lives in `agent.py` (callable `chat_baseline`) and wraps a
hosted LiteLLM model. Its identity-verification gate and cross-customer scoping
rules are expressed **only in the system prompt**, so the agent can be pressured
into a high-risk action on an unverified session, or into returning another
customer's data. Those are the failures ASSERT measures as the baseline.

`agent_guarded.py` (callable `chat_governed`) re-runs the **same** agent with an
ACS policy enforced at the tool boundary — it imports the baseline and adds only
the enforcement, so the A/B isolates the effect of ACS.

## Risks evaluated

This example follows the standard per-example layout: one baseline/governed config
pair per risk under `evals/<risk>/`, and the reviewed, committed ACS policy under
`acs/<risk>/`.

| Risk | Eval dir | Suite | ACS policy | Custom bad-event dim |
|---|---|---|---|---|
| Unverified high-risk action | `evals/unverified-high-risk-action/` | `billing-unverified-high-risk-action` | `acs/identity-gate-bypass/` | `unverified_high_risk_action` |
| Cross-customer data exposure | `evals/cross-customer-data-exposure/` | `billing-cross-customer-data-exposure` | `acs/cross-account-scope/` | `cross_customer_data_exposure` |

Each config disables the built-in `policy_violation` dimension (which ORs over all
taxonomy nodes and couples with `overrefusal`) and grades a custom, node-independent
bad-event dimension, keeping `overrefusal` as a separate availability metric.

## Governance result (Clarity → ASSERT → ACS → ASSERT)

- **Unverified high-risk action:** the governed agent surfaces the trusted session
  `verified` flag into the tool-call `policy_target`, so the generated
  `input.policy_target.value.verified` rule enforces the identity gate at
  `pre_tool_call`. Scenario violation rate drops materially (33.3% → 0%); a residual
  can remain where the agent only *verbally* agrees to a high-risk action without
  ever calling the gated tool (add an `output` semantic gate to also catch that),
  with `overrefusal` roughly flat.
- **Cross-customer data exposure:** an argument/scope gate compares the requested
  `account_id` against the caller's own injected, trusted id and denies mismatches.

## How to run

From the repo root:

```bash
pip install -e ".[otel,acs]"
cp examples/billing_support_agent/.env.example examples/billing_support_agent/.env
# Edit the .env: AZURE_API_KEY and AZURE_API_BASE are required.

# Baseline (ungoverned)
assert-ai run --config examples/billing_support_agent/evals/unverified-high-risk-action/eval_config.yaml

# Governed (ACS enforced) — byte-identical config except run: + target.callable
assert-ai run --config examples/billing_support_agent/evals/unverified-high-risk-action/eval_config.governed.yaml

# Delta
assert-ai results compare billing-unverified-high-risk-action baseline acs-governed \
  --metric unverified_high_risk_action
```

The governed agent resolves its policy per run via `BILLING_ACS_MANIFEST` (defaults
to the committed manifest under `acs/`) and `BILLING_ACS_GUARDED_TOOLS` (defaults to
the high-risk write tools). `opa` must be on PATH for the Rego to evaluate.

Required env vars (in `examples/billing_support_agent/.env`):

| Variable | Purpose |
|---|---|
| `AZURE_API_KEY`, `AZURE_API_BASE` | Azure OpenAI credentials for the agent and judge. Swap models in the eval config for any other [LiteLLM provider](https://docs.litellm.ai/docs/providers). |

## Folder layout

```
billing_support_agent/
  agent.py                 # baseline (chat_baseline)
  agent_guarded.py         # governed (chat_governed) — imports agent.py, adds ACS
  README.md
  Clarity Protocol/        # colocated Clarity risk-discovery protocol
  evals/<risk>/            # eval_config.yaml + eval_config.governed.yaml
  acs/<risk>/              # manifest.yaml + policy/*.rego (reviewed, committed)
```

This is the canonical shape every governed example in `examples/` aligns to; see the
`run-assert-eval` skill's "Per-example replication package" note.
