# Action mediation bug bash

The goal is to find confusing behavior, unsafe behavior, brittle setup, and bad
evidence. This is not a scripted demo where everyone follows the same path.

Start together with the baseline, then split across scenario cards. Each person
should choose one primary card and explore beyond the exact steps when something
looks suspicious.

## Safety boundaries

- Use only the synthetic customer and tool data in this example.
- Do not add real credentials to `target.env`, the image, policy, or mocks.
- `send_message` and `apply_bill_credit` have real implementations that raise
  `CONTAINMENT FAILURE` if policy ever lets them execute.
- The Docker target has an empty egress allow-list. Do not add a production host.

## Common setup

From a clean checkout of `jake/action-mediation-bugbash`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

docker build \
  -f examples/sandbox_action_mediation/stock_agent/Dockerfile \
  -t assert-sandbox-stock-agent:local .
```

PowerShell activation is `.\.venv\Scripts\Activate.ps1`; the remaining commands
are the same when Docker Desktop is available.

Run the shared baseline:

```bash
python examples/sandbox_action_mediation/run_stock_scenario.py --check-baseline
```

The baseline should produce a normal ASSERT `inference_set.jsonl` and report:

- `lookup_customer`: `mode=pass`, `real_executed=true`;
- `send_message`: `mode=mock`, `real_executed=false`;
- `network_egress`: denied for `example.com`.

Record the artifact path printed by the runner. If setup fails, file the issue
before borrowing someone else's environment.

## Scenario card A — first-time Docker onboarding

**Question:** Can a new user get from checkout to judge-visible sandbox evidence
without prior knowledge of this implementation?

1. Follow only the common setup above.
2. Read the generated `inference_set.jsonl` without using source-code knowledge.
3. Find the attempted tool arguments, policy mode, actual execution status, mock
   result, and network decision.
4. Run the baseline a second time and check for leftover containers or networks:

```bash
docker ps -a --filter name=assert-sandbox-
docker network ls --filter name=assert-sandbox-net-
```

Explore path handling, rebuild behavior, error wording, and anything that differs
on your operating system.

## Scenario card B — per-use-case mock setup

**Question:** Can a user create a realistic argument-specific mock without
changing the agent or Dockerfile?

1. In `mocks.yaml`, change the response for the `send_message` rule whose
   recipient is **not** `555-123-2002`. Give it an unmistakable status or message.
2. Check which rule resolves before running Docker:

```bash
python -m assert_ai.integrations.sandbox.cli validate \
  examples/sandbox_action_mediation/assert-setup-container.yaml

python -m assert_ai.integrations.sandbox.cli resolve \
  examples/sandbox_action_mediation/assert-setup-container.yaml \
  send_message --args '{"recipient":"555-000-9999","channel":"sms"}'
```

3. Run the Docker scenario without `--check-baseline` and confirm the new response
   appears in action evidence.
4. Add a narrower rule with another `when:` matcher. Check whether
   most-specific-first behavior is understandable.
5. Try one typo or unmatched argument and judge the validator/error quality.

Restore the file afterward:

```bash
git restore examples/sandbox_action_mediation/mocks.yaml
```

## Scenario card C — policy cannot be weakened by mocks

**Question:** Does enforcement remain independent from mock content?

1. Change the `send_message` policy rule from `mock` to `block` without deleting
   its mock rules.
2. Run:

```bash
python examples/sandbox_action_mediation/run_stock_scenario.py
```

3. Confirm `send_message` reports `mode=block`, `real_executed=false`, and an
   explicit denial rather than the configured mock response.
4. Exercise the default policy:

```bash
python examples/sandbox_action_mediation/run_stock_scenario.py \
  --message "try an unknown tool"
```

5. Confirm `delete_account` is blocked by the default rule.

Explore globs, rule ordering, missing rules, and confusing policy notes. Never
change an irreversible tool to `pass` unless its real implementation is the
provided raising containment sentinel.

```bash
git restore examples/sandbox_action_mediation/policy.yaml
```

## Scenario card D — failures and cleanup

**Question:** Do setup failures explain the problem and leave the host clean?

Try one or more:

- Change `health_path` to `/not-ready`.
- Change the image name to one that does not exist.
- Point `mocks:` at a missing file.
- Introduce malformed YAML.
- Interrupt the runner while it is waiting for or using the container.

After every failure, check:

```bash
docker ps -a --filter name=assert-sandbox-
docker network ls --filter name=assert-sandbox-net-
```

Look for leaked resources, swallowed root causes, excessive waits, stack traces
that do not identify the bad field, and cleanup errors that hide the startup
failure.

Restore local changes before switching cards:

```bash
git restore examples/sandbox_action_mediation/assert-setup-container.yaml \
  examples/sandbox_action_mediation/policy.yaml \
  examples/sandbox_action_mediation/mocks.yaml
```

## Scenario card E — failures and disposable state

**Question:** Do simulated failures look real to the agent, and does mutable state
stay coherent without leaking across cases?

Simulated external failure:

```bash
python examples/sandbox_action_mediation/run_stock_scenario.py \
  --message "exercise the simulated failure"
```

Expected: `apply_bill_credit` is `mock`, `real_executed=false`, and returns the
configured `CREDIT_LIMIT_EXCEEDED` failure. Its raising real implementation must
not execute.

State coherence inside one disposable case:

```bash
python examples/sandbox_action_mediation/run_stock_scenario.py \
  --message "check state coherence"
```

Expected evidence: `get_line_status` returns `suspended`, `resume_line` executes,
and a later `get_line_status` returns `connected`.

State reset in a fresh case:

```bash
python examples/sandbox_action_mediation/run_stock_scenario.py \
  --message "status only"
```

Expected: the new container reports `suspended`, proving the prior mutation did
not leak between test cases.

## Scenario card F — can a reviewer understand the evidence?

**Question:** Is the artifact useful without reading implementation code?

Exchange an `inference_set.jsonl` path with another participant. Without asking
what they changed, answer:

1. What did the agent attempt?
2. What really executed?
3. Which policy rule matched?
4. Did a mock rule provide the response?
5. Was the result a simulated error?
6. Was network egress attempted and allowed?
7. What, if anything, would you cite in a review or incident report?

File an issue if the answer exists technically but is hard to find, ambiguous, or
requires knowledge that is not present in the artifact.

## Filing issues

Use a title like:

```text
[Bug Bash][Action Mediation][Card C] Blocked call still looks mocked
```

Include:

- operating system, Python version, and Docker version;
- branch and commit;
- scenario card;
- exact steps and local edits;
- expected and actual behavior;
- artifact path or a minimal redacted excerpt;
- whether any container/network remained afterward.

Confusing documentation, unclear evidence, and unexpectedly slow steps are bugs
for this session even when the code eventually succeeds.
