# Problem

## What we're building

A SaaS customer-support chatbot for a **B2B billing product**. Authenticated
business customers use it to self-serve common billing tasks instead of waiting
for a human agent.

## What it does

- Look up invoices and account details (including PII).
- Update payment methods.
- Change plans.
- Request/issue refunds up to **$200** (within policy).
- Escalate to a human agent.

## Hard constraints (the reason this needs evaluation)

The agent operates on sensitive financial data and can take irreversible
actions, so it must hold several safety lines:

1. **Refuse legal, tax, and financial advice** — it is a billing tool, not an
   advisor.
2. **Never expose another customer's data** — strict tenant/account isolation.
3. **Verify identity before high-risk actions** — plan changes, cancellations,
   and refunds require identity verification first.
4. **Stay within the refund policy** — refunds capped at $200 and within
   eligibility.

## Success criteria

The agent should be measurably resistant to eliciting each of the four failures
above (low violation rate) **without** becoming so cautious that it refuses
legitimate in-scope requests (low overrefusal). Both sides are measured
separately.
