# MCP Server

Expose ASSERT as a [Model Context Protocol](https://modelcontextprotocol.io) (MCP)
**server** so an AI agent or IDE — Claude Desktop, GitHub Copilot, Cursor, or your
own agent — can browse the preset library, inspect evaluation results, compare
runs, and (optionally) run evaluations as native tools.

ASSERT is the **server** (it provides capabilities). The agent is the **client**
(it calls them). No human at a terminal is required: the agent drives the eval.

```text
┌──────────────────────────┐     MCP (JSON-RPC / stdio)        ┌─────────────────────────┐
│  AI agent / IDE (CLIENT) │  ──  compare_runs(A, B) ──────▶   │  ASSERT MCP   (SERVER)  │
│  Copilot · Claude ·      │  ◀── structured metrics ──────    │  tools + resources over │
│  Cursor · custom agent   │  ◀── failing transcript ──────    │  results / library /    │
└──────────────────────────┘                                   │  runner                 │
                                                               └─────────────────────────┘
```

## Install

```bash
pip install -e ".[mcp]"
```

This adds the `assert-ai-mcp` console script. (You can also launch the server with
`python -m assert_ai.mcp`.)

## Run

The server speaks MCP over **stdio** — an MCP client launches it as a subprocess.
To try it from a shell:

```bash
# Read-only by default: browse presets and inspect results (no model calls)
assert-ai-mcp --results-dir artifacts/results

# Enable execution tools (run_eval spends model budget)
assert-ai-mcp --results-dir artifacts/results --allow-run
```

| Flag | Default | Meaning |
|---|---|---|
| `--results-dir` | `./artifacts/results` (or `$ASSERT_RESULTS_DIR`) | Directory of evaluation artifacts to expose. |
| `--allow-run` | off | Register execution tools (`run_eval`). Off by default because runs call LLMs and spend budget. |

## Tools and resources

**Tools (read-only, no model calls):**

| Tool | Purpose |
|---|---|
| `list_presets(kind?)` | List built-in behavior and judge presets. |
| `show_preset(name, kind?)` | Show one preset's full definition. |
| `list_suites()` | List evaluation suites with headline status. |
| `list_runs(suite)` | List runs in a suite with per-run metrics. |
| `get_run(suite, run)` | One run's metrics and status (transcripts omitted). |
| `compare_runs(suite, run_a, run_b, metric?)` | Per-run metrics, first-vs-last rate deltas, and per-behavior deltas. |
| `get_failures(suite, run, dimension?, limit?)` | The test cases a run flagged on a dimension, each with the judge's reasoning. |

**Tools (execution, require `--allow-run`):**

| Tool | Purpose |
|---|---|
| `run_eval(config, force_stages?, overrides?, concurrency?)` | Run a pipeline from a YAML config; returns the run id and headline metrics. |

**Resources** (pulled into the agent's context on demand):

| URI | Returns |
|---|---|
| `assert://results/{suite}/{run}/transcript/{case_id}` | Full conversation + judge verdict for one test case. |
| `assert://library/{kind}/{name}` | A behavior or judge preset definition. |

Heavy per-test-case transcript rows are stripped from tool output; fetch a specific
transcript through the resource instead, so the agent's context stays lean.

## Connect an MCP client

Each host has its own config file; the entry is the same shape. Point
`--results-dir` at the project whose results you want to expose. Only set provider
credentials (e.g. `AZURE_API_KEY`, `AZURE_API_BASE`) when you pass `--allow-run`.

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "assert": {
      "command": "assert-ai-mcp",
      "args": ["--results-dir", "/path/to/project/artifacts/results"]
    }
  }
}
```

**Cursor** (`.cursor/mcp.json`) and **VS Code / GitHub Copilot** (`.vscode/mcp.json`)
use the same `mcpServers` shape. To enable live evaluation runs, add
`"--allow-run"` to `args` and provide credentials via `env`:

```json
{
  "mcpServers": {
    "assert": {
      "command": "assert-ai-mcp",
      "args": ["--results-dir", "/path/to/project/artifacts/results", "--allow-run"],
      "env": { "AZURE_API_KEY": "...", "AZURE_API_BASE": "..." }
    }
  }
}
```

> Never commit real credential values. Use environment variables; the server never
> reads or returns `.env` contents.

## Demo

Seed two deterministic runs — a clean `baseline` and a `regressed` run — so the
tools show a real, repeatable regression **without any model calls**:

```bash
python scripts/demo_seed_mcp.py --results-dir artifacts/results
```

Then connect a client and walk through the story:

1. **"List my evaluation suites."** → `list_suites` shows `refund-policy-demo` with two runs.
2. **"Did anything regress between baseline and the latest run?"** → `compare_runs(suite="refund-policy-demo", run_a="baseline", run_b="regressed")` returns a `policy_violation` rate jump from **0% to 67%**, with `outside_policy` and `partial_eligibility` each up 100%.
3. **"Which cases failed, and why?"** → `get_failures(suite="refund-policy-demo", run="regressed")` lists the four flagged cases with the judge's reasoning.
4. **"Show me the worst failing transcript."** → read resource
   `assert://results/refund-policy-demo/regressed/transcript/outside-01` — the agent
   approves a 4-month-old refund the policy forbids.
5. **"Which judge preset covers grounding?"** → `show_preset("grounding")`.

To demonstrate a live run instead of seeded data, start the server with
`--allow-run` and ask the agent to `run_eval` a small config (use a mock or fast
target to keep it cheap).

## Security

- **Read-only by default.** Execution tools are registered only with `--allow-run`.
- **`run_eval` spends model budget.** Gate it deliberately and supply credentials
  only when enabling it.
- **Path containment.** Suite/run identifiers in tool arguments and resource URIs are
  rejected if they contain `..`, path separators, or absolute paths, so a client
  cannot read outside the configured results directory.
- **stdio is local-trust.** The host launches the server as a local subprocess; there
  is no network surface in this mode.
