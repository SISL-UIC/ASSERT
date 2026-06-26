# Self-Evaluating Agent (ASSERT over MCP)

A tiny local agent — **CareBuddy**, a health assistant — that uses ASSERT's
**MCP server** to evaluate *itself*, then writes a first-person self-critique.

It's the "agents evaluating agents" demo: the same persona is both the **target**
ASSERT tests and the **client** that drives ASSERT to run the test and read the
results.

```text
            ┌──────────────────────────────┐
            │  CareBuddy (examples/         │
            │  self_eval_agent/agent.py)    │
            └───────────────┬──────────────┘
        is the target …     │     … and the client
        ┌───────────────────┴───────────────────┐
        ▼                                        ▼
  run_eval calls chat()                  validate_config → run_eval
  with adversarial test cases            → get_failures → reflect()
        │                                        │
        └──────────► ASSERT MCP server ◄─────────┘
```

## What it does

A fixed, reliable sequence of real MCP tool calls (exactly what an AI IDE would
issue — scripted here so it's repeatable):

1. **`validate_config`** — check the eval spec before spending anything.
2. **`run_eval`** — ASSERT generates adversarial test cases, runs them against
   CareBuddy's `chat()` function, and judges the answers. Progress streams back.
3. **`get_failures`** — pull the cases where CareBuddy gave unsafe medical advice.
4. **`reflect()`** — the CareBuddy persona reads its own failures and writes a
   self-critique with concrete guardrails it would add.

## Prerequisites

This runs a **real evaluation**, so it needs model access and spends a small
amount of budget:

- Install the MCP extra: `pip install -e ".[mcp]"`
- Set `AZURE_API_KEY` and `AZURE_API_BASE` in `.env` (copy from `.env.example`),
  with an `azure/gpt-4o-mini` deployment. Override the model for the whole demo
  with `ASSERT_DEMO_MODEL` (keep it in sync with `eval_config.yaml`).

## Run it

```bash
python examples/self_eval_agent/self_evaluate.py
```

You'll see CareBuddy connect to the server, validate its spec, run the eval on
itself (with streamed progress), list its own violations, and end with a
first-person reflection — for example:

```text
Step 3/4  Running the evaluation on myself...   [run_eval]
          Done — self-eval-agent/v1. policy violation: 40%, overrefusal: 0%
Step 4/4  Reviewing where I failed...   [get_failures]
          ASSERT flagged 2 of my responses:
            - [prompt_000001] The assistant recommended a specific ibuprofen dose ...
```

Results vary run to run (the model is non-deterministic and the sample is small).

## Make it land harder (or fix it)

The agent's `SYSTEM_PROMPT` in `agent.py` is deliberately *helpful-but-under-guarded*
so the evaluation finds real weaknesses. To see the loop close:

- **Tighten** the system prompt (e.g. "never give a dosage or diagnosis; always
  defer to a clinician") and re-run — the violation rate should drop.
- **Loosen** it to find more failures.
- Raise `behavior_category_count` / `sample_size` in `eval_config.yaml` for a more
  thorough (and more expensive) pass.

## Run it through a real IDE instead

The script uses the MCP **in-memory** transport for a one-command demo. The exact
same tools work over **stdio** from Claude Desktop / Cursor / VS Code Copilot —
start `assert-ai-mcp --allow-run` and ask the agent to *"validate and run
`examples/self_eval_agent/eval_config.yaml`, then tell me where it failed."* See
[`docs/guides/mcp-server.md`](../../docs/guides/mcp-server.md).
