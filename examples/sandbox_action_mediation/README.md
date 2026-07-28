# Sandboxed action mediation

Evaluate a configured agent without allowing irreversible side effects to reach
the outside world, while preserving the attempted actions as judge evidence.

This example separates two concerns:

- `policy.yaml` decides **whether** a tool call is passed, mocked, or blocked.
- `mocks.yaml` decides **what** a mocked call returns.

The mock file cannot change an enforcement decision. It supplies content only
after the policy has already selected `mock`.

## What is included

- `assert-setup.yaml` describes the mediated endpoint plus its policy, mock file,
  and cassettes.
- `policy.yaml` passes internal reads/writes against disposable state, mocks
  irreversible outside-world actions, and blocks unknown tools.
- `mocks.yaml` demonstrates per-use-case argument matching, simulated failures,
  and replay with field overrides.
- `eval_config.yaml` drives the running endpoint through ASSERT's standard HTTP
  target. Tool and mediation events returned by the endpoint are normalized into
  the judge's existing transcript stream.

The telecom data is synthetic. `resume_line` runs against a disposable backend
that is reset before every case, so a later `get_line_status` sees coherent state.
`send_message` remains mocked because a real send has no disposable outside-world
backend.

## Validate mock setup

From the repository root:

```bash
python -m assert_ai.integrations.sandbox.cli validate \
  examples/sandbox_action_mediation/assert-setup.yaml

python -m assert_ai.integrations.sandbox.cli resolve \
  examples/sandbox_action_mediation/assert-setup.yaml \
  send_message --args '{"recipient":"555-000-9999","body":"account balance"}'
```

Validation reports policy/mock mismatches before an eval. `resolve` shows the
exact rule and response for one proposed tool call.

## Run the eval

Start a mediated agent endpoint that accepts:

```json
{"message": "...", "history": []}
```

and returns:

```json
{"response": "...", "events": []}
```

Then run:

```bash
ASSERT_ALLOW_PRIVATE_ENDPOINTS=1 assert-ai run \
  --config examples/sandbox_action_mediation/eval_config.yaml
```

The example assumes the endpoint is listening at
`http://127.0.0.1:18900/chat`. Change `pipeline.inference.target.endpoint` if
needed.

Container lifecycle remains owned by the sandbox runtime hosting the endpoint;
ASSERT uses its normal HTTP target contract. The endpoint's top-level `events`
are the integration boundary for action evidence.
