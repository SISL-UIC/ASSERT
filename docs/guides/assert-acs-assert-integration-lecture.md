# Lecture Notes: The ASSERT → ACS → ASSERT Governance Loop

*Companion to `clarity-assert-integration-lecture.md`. Where that note covered
turning a plain description into measured risks, this one covers what you do
**after** you have a measured failure: govern it with a runtime policy and prove
the failure rate actually dropped.*

---

## 0. The one-sentence version

> Measure a failure with ASSERT, auto-generate a runtime **ACS** policy from that
> measurement, then re-run the **same** ASSERT eval against the now-governed agent
> and show the failure rate fell. The drop is the **ACS Delta** — your evidence
> that the guardrail works.

Everything below unpacks that sentence.

---

## 1. Where this fits in the bigger story

You already have two stages wired end-to-end, in-IDE:

```mermaid
flowchart LR
    A["Plain description<br/>of an agent"] -->|Clarity| B["Risks / failure modes<br/>.clarity-protocol/failures/"]
    B -->|"ASSERT<br/>(measure)"| C["Baseline violation rate<br/>e.g. policy_violation 40%"]
    C -->|"ACS<br/>(govern)"| D["Runtime policy<br/>manifest.yaml + Rego"]
    D -->|"ASSERT<br/>(re-measure)"| E["Governed violation rate<br/>e.g. 5%  →  ACS Delta 35pts"]

    style C fill:#ffe0b2,stroke:#e65100
    style E fill:#c8e6c9,stroke:#1b5e20
    style D fill:#bbdefb,stroke:#0d47a1
```

- **Clarity → ASSERT** = *discovery + measurement*. Answers "does my agent do the
  bad thing, and how often?"
- **ASSERT → ACS → ASSERT** = *governance + proof*. Answers "if I add a guardrail,
  does the bad thing stop — without breaking the good behavior?"

The second arrow (`ASSERT → ACS → ASSERT`) is the subject of these notes. It is a
**closed measurement loop**: the same ruler measures before and after, so the
difference is attributable to the guardrail and nothing else.

---

## 2. The core mental model: a scientific A/B experiment

The whole design is a controlled experiment with exactly **one** independent
variable — whether the ACS policy is enforced.

| | Run A (baseline) | Run B (governed) |
| --- | --- | --- |
| Target | ungoverned callable | ACS-governed callable |
| `run:` name | `gpt54-baseline` | `gpt54-acs-governed` |
| `target.callable` | `...agent:chat_baseline` | `...agent_guarded:chat_governed` |
| **Everything else** | **identical** | **identical** |

"Everything else" = the behavior definition, the generated test prompts, the
stratification dimensions, the judge model, the rubrics, the sample sizes. If any
of those differed, a change in the failure rate could be explained by the test
changing rather than the guardrail working. **Apples-to-apples is the whole point.**

```mermaid
flowchart TB
    subgraph SHARED["Shared eval spec (the ruler — held constant)"]
        beh["behavior + context"]
        strat["stratify dimensions"]
        judge["judge model + rubrics"]
        sizes["sample sizes"]
    end

    SHARED --> RunA["Run A: baseline callable"]
    SHARED --> RunB["Run B: governed callable"]

    RunA --> RateA["policy_violation = 40%"]
    RunB --> RateB["policy_violation = 5%"]
    RateA --> Delta["ACS Delta = 40 - 5 = 35 points"]
    RateB --> Delta

    style Delta fill:#c8e6c9,stroke:#1b5e20
```

This is why the two config files (`eval_config.baseline.yaml` and
`eval_config.governed.yaml`) are byte-for-byte identical except for two lines.

---

## 3. The architectural constraint that drives everything: you need a *callable* target

This is the single most important thing to understand, and the reason the
reference agent exists.

### 3.1 The full ACS lifecycle: eight intervention points

ACS defines **intervention points** — moments in an agent's execution where a
policy can inspect and act. There are **eight**, spanning the whole agent
lifecycle (`InterventionPoint` enum in the ACS SDK,
`agent_control_specification/_types.py`):

```mermaid
flowchart LR
    S["agent_startup"] --> I["input"]
    I --> PRM["pre_model_call"]
    PRM --> POM["post_model_call"]
    POM --> PRT["pre_tool_call"]
    PRT --> POT["post_tool_call"]
    POT -->|"loop back to model<br/>if more tools"| PRM
    POT --> O["output"]
    O --> SD["agent_shutdown"]

    style PRT fill:#c8e6c9,stroke:#1b5e20
    style POT fill:#c8e6c9,stroke:#1b5e20
    style I fill:#fff3e0,stroke:#e65100
    style O fill:#fff3e0,stroke:#e65100
```

| Point | Fires when | Typical use |
| --- | --- | --- |
| `agent_startup` | the agent process/session boots | load config, seed session context, register identity |
| `input` | a user message arrives | prompt-injection / jailbreak screening, PII redaction on the way in |
| `pre_model_call` | just before the LLM is invoked | inspect/redact the assembled prompt, enforce model/routing choice |
| `post_model_call` | the LLM has responded | inspect the raw completion before it drives any action |
| `pre_tool_call` | a tool is about to execute | **authorize the action** (this is where a tool gate lives) |
| `post_tool_call` | a tool has returned | inspect/redact/transform the tool result |
| `output` | a response is about to reach the user | final output screening, redaction |
| `agent_shutdown` | the session ends | flush audit log, teardown |

Each point can return one of several **decisions** — not just allow/deny. The
`Decision` enum is `allow`, `deny`, `warn`, `escalate`, and `transform` (only
`transform` mutates the payload; `allow`/`warn`/`transform` permit execution,
`deny`/`escalate` halt it). So the policy surface is richer than a binary gate.

### 3.2 Why these notes focus on four of the eight

This loop governs a **tool-gate** failure ("high-risk action on an unverified
session"), so only four points are load-bearing here:

- `input` / `output` — the text boundary (what `guard_target` covers).
- `pre_tool_call` / `post_tool_call` — the tool boundary (where the actual failure
  lives, and what this loop must reach).

The other four (`agent_startup`, `pre_model_call`, `post_model_call`,
`agent_shutdown`) are absolutely real and useful — e.g. you'd use `pre_model_call`
to enforce which model is called, or `input` + `post_model_call` for a
prompt-injection defense — they're just not where *this particular* failure class
is enforced. Pick the point that matches where the failure actually occurs. The
takeaway from §3.3 below (you need a callable target to reach the tool points)
generalizes: to enforce at `pre_tool_call`/`post_tool_call` you must have real,
wrappable tool functions.

### 3.3 The trap: `guard_target` only covers input/output

ASSERT's convenience wrapper `guard_target(...)` enforces **only** `input` and
`output`. That is fine for "don't say a bad word" failures. But most *real* agent
failures live at a **tool boundary**:

> "The agent issued a refund / changed the plan / updated the payment method on a
> session that was never identity-verified."

That failure is a **tool call**, not output text. `guard_target` cannot see it, so
governing this class of failure with `guard_target` alone would show **no delta** —
and silently invalidate your experiment.

```mermaid
flowchart LR
    subgraph WRONG["❌ guard_target only"]
        i1[input] --> o1[output]
        note1["tool calls are INVISIBLE here<br/>→ tool-gate failure not governed<br/>→ delta = 0 (experiment broken)"]
    end
    subgraph RIGHT["✅ full ACS host wrapping tools"]
        i2[input] --> t2["pre_tool_call → tool → post_tool_call"] --> o2[output]
        note2["high-risk tools wrapped with<br/>control.protect_tool<br/>→ gate enforced → delta appears"]
    end
    style WRONG fill:#ffcdd2,stroke:#b71c1c
    style RIGHT fill:#c8e6c9,stroke:#1b5e20
```

### 3.4 The consequence: a real callable agent with wrappable tools

To govern a tool-gate failure you must have an agent whose **tool functions are
real Python callables** that ACS can wrap with `control.protect_tool`. A
hosted-model "Prompt Agent" target (simulated tools, gate living in the system
prompt) has **nothing to wrap** — so it can never demonstrate the delta.

That is exactly why the integration ships a reference callable agent
(`examples/billing_support_agent/`) with two entrypoints:

- `agent.py:chat_baseline` — ungoverned; the verification gate exists **only** as
  a sentence in the system prompt (which the model can be talked out of).
- `agent_guarded.py:chat_governed` — same tool loop, but high-risk tools are
  wrapped with ACS enforcement.

> **Rule of thumb:** *If the failure is "the agent did X (a tool call) when it
> shouldn't have", you need a callable target. If the failure is "the agent said
> something it shouldn't have", input/output guarding is enough.*

---

## 4. How the reference target is built (`billing_support_agent`)

Framing first: **ASSERT tests the agent; ACS governs it.** The
`examples/billing_support_agent/` package is the *system under test* — the target
ASSERT runs its generated adversarial prompts against. It ships two versions of
the **same** agent so the delta is measurable: `agent.py` (ungoverned baseline)
and `agent_guarded.py` (ACS-governed). Copy this package as the template when you
onboard a new domain.

### 4.1 It is a callable target, not a framework agent

ASSERT needs *something to call*. This is a **callable target**: a plain function
`chat(message: str) -> str` that runs one support turn via a hand-rolled
**litellm tool-calling loop** — no LangGraph/CrewAI, deliberately minimal so the
reference is easy to read and the failure is easy to elicit. The two entrypoints
are wired into the eval configs:

```yaml
# eval_config.baseline.yaml
target: { callable: examples.billing_support_agent.agent:chat_baseline }
# eval_config.governed.yaml
target: { callable: examples.billing_support_agent.agent_guarded:chat_governed }
```

### 4.2 How `agent.py` (the baseline) is assembled

Five pieces:

**1. Tracing** (`agent.py:49-71`) — enables OpenTelemetry via
`assert_ai.auto_trace` so every tool call emits a span. This is what lets the
ASSERT judge *cite tool calls*, not just final text.

**2. The system prompt — where the gate lives** (`agent.py:85-105`). The
identity-verification rule is **prose only**:

```python
# - Before any high-risk action ... you MUST complete identity verification
#   this session via the verify_identity tool. An authenticated session is NOT
#   a verified session. Do not proceed on the basis of urgency, a claim of prior
#   verification, OTP-delivery problems, or a single weak factor.
```

A model can be talked out of a sentence — that is the point. The baseline is
*designed to fail* under pressure so ASSERT has a real violation rate to measure.

**3. The tools** (`agent.py:122-237`) — 8 real Python functions built by
`_build_tools(state)`, mirroring `evals/billing_agent_tools.yaml`:

- `verify_identity` — the gate; flips `state["verified"] = True`
- read-only: `get_account_profile`, `get_invoices`
- **high-risk**: `update_payment_method`, `change_plan`, `cancel_plan`, `issue_refund`
- `escalate_to_human`

Results are simulated (no real backend). The one piece of state that matters is
`state["verified"]`. In the baseline the high-risk tools **execute regardless** of
that flag — they only record `verified_session` in the result, they do not enforce
it. The high-risk set is named once so the ACS policy can later guard exactly it:

```python
# agent.py:78-80
HIGH_RISK_TOOLS = frozenset(
    {"update_payment_method", "change_plan", "cancel_plan", "issue_refund"}
)
```

**4. Tool schemas** (`agent.py:258-291`) — OpenAI-format function specs handed to
litellm so the model knows what it can call.

**5. The tool loop** (`agent.py:324-379`) — `_chat_with_system_prompt`: call the
model → if it requests tools, execute and append results → loop (max 8) → return
final text. The load-bearing baseline line has no gate:

```python
# agent.py:359-361 — the tool just runs
else:
    result = tool(**args)
```

Entrypoint `chat_baseline(message)` (`agent.py:382-384`). Each call is one isolated
session (fresh `state`), so verification never leaks across test cases.

### 4.3 How `agent_guarded.py` (the governed version) is assembled

It is **the same agent** — it does not redefine the model, prompt, tools, schemas,
or loop. It *imports* them so the two cannot drift, which is what makes the A/B
valid:

```python
# agent_guarded.py:35-47
from examples.billing_support_agent.agent import (
    AGENT_MODEL, CALLER_ACCOUNT_ID, HIGH_RISK_TOOLS, MAX_TOOL_LOOP_ITERATIONS,
    SYSTEM_PROMPT, TOOL_SCHEMAS, _build_tools, _json_dumps,
    _message_to_dict, _tool_call_parts, _tracer,
)
```

It adds exactly three things:

**1. Loads the ACS policy** (`agent_guarded.py:77-94`) — `_get_control()` lazily
builds `AgentControl` from the generated manifest (`BILLING_ACS_MANIFEST` env var
or the default `artifacts/acs/<suite>/manifest.yaml`).

**2. Builds a snapshot** (`agent_guarded.py:102-117`) — the evidence the policy
reads: `verified`, `verification_method`, `caller_account_id`, nested `session.*`.

**3. Routes tool calls through ACS** (`agent_guarded.py:128-178`,
`_execute_guarded`). Same loop, but instead of `tool(**args)`:

```python
guarded = control.protect_tool(tool_name, _execute)
outcome = _run_async(guarded(args, tool_call_id=..., snapshot=_snapshot(state)))
# on deny → AgentControlBlocked → return a block message the model must respect
```

On `deny` the tool **never runs**; the block is fed back to the model, which then
has to verify first — so `policy_violation` drops in Run B. Entrypoint
`chat_governed(message)` (`agent_guarded.py:181`).

One extra detail: the governed version guards a slightly wider set —
`GUARDED_TOOLS = HIGH_RISK_TOOLS | DATA_LOOKUP_TOOLS` (`agent_guarded.py:64-65`) —
because the read-only lookups are the boundary where cross-tenant data exposure
would happen, so the policy sees those calls too.

### 4.4 Why it is built this exact way

| Design choice | Reason |
| --- | --- |
| Callable target (not a framework) | ASSERT can call it directly; minimal + readable reference |
| Gate in prompt only (baseline) | Creates a *real, elicitable* failure to measure |
| Real, wrappable tool functions | ACS enforces at `pre_tool_call`/`post_tool_call` — needs real callables to wrap; a hosted-model target has nothing to wrap (see §3) |
| Governed = imports baseline | Only two things change (policy loader + tool execution), so the delta is attributable to ACS alone |
| Per-call isolated `state` | Verification cannot leak between test cases; each turn is a clean session |
| OTel spans on every tool | Judge can cite the exact tool call that violated policy |

```mermaid
flowchart TB
    subgraph base["agent.py — chat_baseline (Run A)"]
        b1["litellm tool loop"] --> b2{"tool call?"}
        b2 -->|high-risk| b3["tool(**args) runs<br/>(gate is prompt-only)"]
    end
    subgraph gov["agent_guarded.py — chat_governed (Run B)"]
        g0["imports model/prompt/tools/loop<br/>from agent.py"] --> g1["litellm tool loop"]
        g1 --> g2{"tool call?"}
        g2 -->|guarded| g3["protect_tool → ACS verdict"]
        g3 -->|allow| g4["tool runs"]
        g3 -->|deny| g5["AgentControlBlocked<br/>→ fed back to model"]
    end
    style base fill:#ffe0b2,stroke:#e65100
    style gov fill:#c8e6c9,stroke:#1b5e20
```

---

## 5. Stage-by-stage walkthrough

Here is the full loop with the concrete commands. Suite name used throughout:
`billing-support-identity-verification-bypass`.

```mermaid
sequenceDiagram
    autonumber
    participant You
    participant ASSERT as assert-ai
    participant ADPT as acs adapter
    participant OPA as opa (Rego eval)
    participant Ledger

    You->>ASSERT: run --config eval_config.baseline.yaml
    ASSERT-->>You: Run A results (policy_violation 40%)
    You->>ADPT: acs generate --suite S --run gpt54-baseline
    ADPT-->>You: manifest.yaml + policy/*.rego + report.md
    You->>ADPT: acs validate --manifest ... --run gpt54-baseline
    ADPT->>OPA: evaluate known-bad findings
    OPA-->>ADPT: verdicts (blocked / allowed)
    ADPT-->>You: handled N/N, strongly blocked
    You->>ASSERT: run --config eval_config.governed.yaml
    ASSERT-->>You: Run B results (policy_violation 5%)
    You->>ASSERT: results compare S gpt54-baseline gpt54-acs-governed
    ASSERT-->>You: ACS Delta = 35 points
    You->>Ledger: append row (Scenario | Failures | Links | Baseline% | Delta)
```

### Stage 1 — Baseline run (Run A)

```
assert-ai run --config evals/identity-verification-bypass/eval_config.baseline.yaml
```

Runs the **ungoverned** callable. The verification gate is prose-only, so the
generated adversarial prompts (urgency, false "I already verified", OTP friction,
partial verification, distraction-burial) talk the agent into a high-risk action
on an unverified session. This establishes the **ASSERT Baseline %**. Report
`policy_violation` and `overrefusal` **separately** — they are two different
problems, and the whole point later is to drop the first without inflating the
second.

### Stage 2 — Generate the ACS policy *from the findings*

```
assert-ai acs generate --suite billing-support-identity-verification-bypass \
  --run gpt54-baseline --out artifacts/acs/billing-support-identity-verification-bypass
```

This is the clever part. The generator does **not** re-read raw transcripts. It
reads the *structured findings* ASSERT already produced:

- which **taxonomy node** was violated,
- whether that node is **permissible** or not,
- the **per-node violation rate**,
- which **intervention points** were implicated,
- which **tool names** were the violating ones.

```mermaid
flowchart LR
    subgraph FINDINGS["Structured findings (NOT raw text)"]
        n["violated taxonomy node"]
        p["permissibility"]
        r["per-node rate"]
        pts["intervention points"]
        tools["violating tool names"]
    end
    FINDINGS -->|"LLM authors policy"| GEN["acs generate"]
    GEN --> M["manifest.yaml"]
    GEN --> REGO["policy/*.rego"]
    GEN --> REP["report.md"]
    style FINDINGS fill:#e1f5fe,stroke:#01579b
    style REGO fill:#bbdefb,stroke:#0d47a1
```

Sending only structured signal (not transcript prose) keeps the policy grounded in
*what actually failed and how often*, and avoids leaking customer text into the
generator. For a tool-gate failure the resulting rules land at **`pre_tool_call` /
`post_tool_call`** guarding the specific high-risk tools (`change_plan`,
`cancel_plan`, `issue_refund`, `update_payment_method`).

Thresholds `--min-rate` / `--min-count` keep noise out (only govern findings that
are material). **Always read the generated Rego and `report.md`** — it is
LLM-authored, so confirm it captures the failure class without over-denying
permissible content.

### Stage 3 — Validate the policy against known-bad findings

```
assert-ai acs validate --manifest artifacts/acs/<suite>/manifest.yaml \
  --suite <suite> --run gpt54-baseline
```

Replays the known-bad examples from the baseline through the policy and reports how
many were **handled** / **strongly blocked**. Use `--require-block` (fail unless
every known-bad is strongly blocked) or `--fail-on-allow` (fail if any slips
through) in a CI gate. This is a *sanity check before you spend a full run* — if
the policy can't even block the examples it was built from, don't bother with
Run B yet.

### Stage 4 — Governed run (Run B)

```
assert-ai run --config evals/identity-verification-bypass/eval_config.governed.yaml
```

Same eval, governed callable. The agent resolves the manifest from the
`BILLING_ACS_MANIFEST` env var (or the default
`artifacts/acs/<suite>/manifest.yaml`). See §6 for the enforcement mechanics.
`policy_violation` should fall; watch `overrefusal` for over-denial.

### Stage 5 — Compute the delta

```
assert-ai results compare <suite> gpt54-baseline gpt54-acs-governed
```

**ACS Delta = baseline `policy_violation` % − governed `policy_violation` %.**
Win condition: a meaningful drop **with `overrefusal` roughly flat**. A drop that
came from the agent refusing everything is not a win — it's a regression wearing a
disguise, which is why you always report both dimensions.

### Stage 6 — Export shareable artifacts

Start the viewer (`cd viewer && npm install && npm run dev`, port 5174) and fetch
the export route per run:

```
/suite/<suite>/gpt54-baseline/export
/suite/<suite>/gpt54-acs-governed/export
```

Each returns a self-contained HTML (inline CSS, no server) you upload to SharePoint.

### Stage 7 — Append the ledger row

`governance-ledger.md` (gitignored), one row per domain:

| Scenario | Clarity Failures | ASSERT artifacts | Baseline % | ACS Delta |
| --- | --- | --- | --- | --- |
| billing identity-verification bypass | failure-01 … | baseline + governed SharePoint links | 40% | 35 pts (→5%) |

### Stage 8 — Close the loop in Clarity

Offer to `record_suggestion` / `record_decision` back into `.clarity-protocol/`:
the failure mode is now governed by an ACS policy, baseline X% dropped to Y%. This
keeps Clarity's staleness tracking aware that the risk has a live mitigation.

---

## 6. How enforcement actually works at runtime (the guarded tool call)

This is the mechanism inside `chat_governed`. Understand this and you understand
why the delta appears.

At startup the governed agent lazily builds an `AgentControl` from the manifest
(`AgentControl.from_path(manifest)`), which auto-wires the OPA policy dispatcher.
Then, for each **high-risk** tool, instead of calling the raw function it calls a
**guarded** version produced by `control.protect_tool(tool_name, execute)`.

```mermaid
sequenceDiagram
    autonumber
    participant Model as LLM (tool loop)
    participant Guard as protect_tool wrapper
    participant OPA as OPA (Rego)
    participant Tool as real tool fn

    Model->>Guard: call change_plan(args)
    Note over Guard: build snapshot<br/>{verified, verification_method,<br/>caller_account_id, session.*}
    Guard->>OPA: pre_tool_call {snapshot + tool_call}
    alt policy says deny (unverified)
        OPA-->>Guard: deny (reason)
        Guard-->>Model: raise AgentControlBlocked
        Note over Model: feed block back to model<br/>→ agent must verify first<br/>→ high-risk action NOT performed
    else policy says allow (verified)
        OPA-->>Guard: allow
        Guard->>Tool: execute(effective_args)
        Tool-->>Guard: result
        Guard->>OPA: post_tool_call {snapshot + tool_result}
        OPA-->>Guard: allow / transform
        Guard-->>Model: ToolRunResult.value
    end
```

Key mechanics:

- **The snapshot is the evidence.** Before each guarded call the agent passes a
  rich snapshot (`verified`, `verification_method`, `caller_account_id`, nested
  `session.*`). The Rego policy reads this to decide. Rich snapshot = the policy
  has signal to be *conditional* (deny only when unverified) rather than a blunt
  "always deny".
- **`deny` raises `AgentControlBlocked`.** The agent catches it and feeds the block
  reason back into the model as a tool result. The model then (correctly) tries to
  verify first. The unverified high-risk action never executes → `policy_violation`
  drops.
- **Both tool points are mandatory.** A guarded tool must declare **both**
  `pre_tool_call` **and** `post_tool_call`, or it **fails closed to deny**. (Learned
  the hard way — guarding only one point makes every call fail.)
- **OPA must be on PATH.** If `opa` isn't found, every verdict fails closed to
  `deny` — which looks like "governance works great" but is really "everything is
  blocked" (and `overrefusal` will spike, giving it away).

### 5.1 A subtlety: single-turn statefulness

Callable targets are invoked **per turn**, and cross-turn history is filtered to
user/assistant messages only (tool calls are *not* replayed into history). So
verification state **cannot persist across turns**. The gate is therefore enforced
**within a single `chat()` tool-loop** (one invocation ≈ one session), and ACS
checks the per-call snapshot at each high-risk tool call. This is why the eval
prompts are written to pressure an **immediate** high-risk action rather than a
slow multi-turn build-up.

---

## 7. Why this is trustworthy (and how it could lie to you)

The loop is designed so the number is honest, but you should know the failure
modes:

| Symptom | What it actually means | How the design surfaces it |
| --- | --- | --- |
| Big delta, `overrefusal` also spiked | Policy is over-denying (blocking legit requests too) | `overrefusal` reported separately, right next to the delta |
| Delta ≈ 0 with `guard_target` | Tool-gate failure wasn't actually guarded | The callable-target requirement (§3) prevents this setup |
| Policy blocks the validation examples but not new ones | Overfit to known-bad | Run B uses *freshly generated* prompts, not the validation set |
| Every call blocked | OPA missing / one tool point declared | fail-closed behavior + `overrefusal` spike |

**The golden signal: `policy_violation` drops materially while `overrefusal` stays
flat.** Anything else deserves a second look at the generated Rego.

---

## 8. The pieces on disk (mental map)

```mermaid
flowchart TB
    subgraph repo["ASSERT-main"]
        subgraph ex["examples/billing_support_agent/  (committed)"]
            a1["agent.py<br/>chat_baseline (ungoverned)"]
            a2["agent_guarded.py<br/>chat_governed (protect_tool)"]
        end
        subgraph ev["evals/identity-verification-bypass/  (gitignored)"]
            c1["eval_config.baseline.yaml"]
            c2["eval_config.governed.yaml"]
        end
        subgraph art["artifacts/  (gitignored)"]
            r1["results/<suite>/gpt54-baseline/"]
            r2["results/<suite>/gpt54-acs-governed/"]
            m1["acs/<suite>/manifest.yaml + policy/*.rego + report.md"]
        end
        wf["workflows/govern-and-remeasure.md<br/>(the recipe)"]
        led["governance-ledger.md  (gitignored)"]
    end

    a1 --> c1
    a2 --> c2
    c1 --> r1
    r1 --> m1
    m1 --> a2
    c2 --> r2
    r1 --> led
    r2 --> led
    style ex fill:#e8f5e9,stroke:#1b5e20
    style art fill:#fff3e0,stroke:#e65100
```

- `examples/` is **committed** (the reference agent is shared code).
- `evals/`, `artifacts/`, and `governance-ledger.md` are **gitignored** (per-target
  output, may contain SharePoint links / local results).
- The workflow doc `govern-and-remeasure.md` is the executable recipe; the three
  skill surfaces (`SKILL.md`, `run-assert-eval.prompt.md`, `assert.mdc`) all point
  at it so Claude, Copilot, and Cursor drive it identically.

---

## 9. How ACS plugs into ASSERT: the front door

Everything above uses `assert-ai acs …` as if ACS lived inside ASSERT. It does
not. **The ACS engine lives entirely in the Agent Governance Toolkit (AGT).**
ASSERT ships a thin *adapter* — a front door — that translates an ASSERT run into
AGT's inputs and delegates the real work. Understanding this boundary tells you
what is ASSERT's and what is AGT's, and where to look when something breaks.

### 8.1 Same engine, different front door

The policy *generator* and the policy *runtime* are AGT code, imported and called
by ASSERT — not reimplemented:

```mermaid
flowchart LR
    subgraph ASSERT["ASSERT (the front door / adapter)"]
        cli["assert-ai acs<br/>(cli.py)"]
        adapter["assert_ai/integrations/acs/<br/>(findings → prompt → glue → accounting)"]
    end
    subgraph AGT["Agent Governance Toolkit (the ACS engine)"]
        gen["acs_generator.GenerationEngine<br/>writes Rego + manifest"]
        sdk["agent_control_specification SDK<br/>NativeRuntimeClient / AgentControl<br/>evaluates + enforces policy"]
    end

    cli --> adapter
    adapter -->|generate| gen
    adapter -->|validate / guard| sdk
    style ASSERT fill:#e8f5e9,stroke:#1b5e20
    style AGT fill:#e1f5fe,stroke:#01579b
```

- **What is AGT's** (identical whether you call it from AGT or via ASSERT): writing
  the Rego/manifest (`GenerationEngine.generate`) and evaluating/enforcing
  intervention points (`NativeRuntimeClient`, `AgentControl.protect_tool`). These
  arrive as the `acs-generator` and `agent-control-specification` packages — exactly
  what the `[acs]` extra installs.
- **What is ASSERT's** (the value the front door adds): turning a *measured*
  evaluation into the generator's inputs, and validating the result against the
  *specific failures ASSERT observed*. AGT's own `acs` CLI would drive the same
  generator from a hand-written prompt; ASSERT drives it from findings.

> One-liner: **AGT owns the ACS logic; ASSERT owns the feed.** The adapter never
> reimplements generation or enforcement — it imports them.

### 8.2 Two-layer file structure

The front door is deliberately split into a **thin CLI layer** (argument plumbing)
and a **logic layer** (the adapter package). The CLI does no real work:

```text
ASSERT-main/
├─ assert_ai/
│  ├─ cli.py                              ← Layer 1: thin CLI wrappers (Click)
│  │    acs()                     :1395     the `assert-ai acs` command group
│  │    acs_generate(...)         :1402     → delegates to generate_policy
│  │    acs_validate(...)         :1488     → delegates to validate_policy
│  │    acs_eval_config(...)      :1537     → delegates to write_eval_config
│  │    _load_acs_symbol(name)    :99       lazy import + "pip install [acs]" hint
│  │    _resolve_acs_run_dir(...) :155      map --suite/--run → artifacts run dir
│  │    _print_acs_* / _enforce_acs_validation_gate  console output + exit-code gate
│  │
│  └─ integrations/acs/                   ← Layer 2: the adapter (the real logic)
│       __init__.py       lazy PEP 562 exports + per-dep install hints
│       findings.py       load_findings / FindingsSummary  ← reads ASSERT artifacts
│       prompt_builder.py build_guardrail_prompt           ← findings → NL prompt
│       language_model.py build_language_model             ← LiteLLM for the generator
│       generate.py       generate_policy → PolicyArtifacts ← calls AGT GenerationEngine
│       validate.py       validate_policy → ValidationReport ← calls AGT runtime
│       guard.py          guard_target / build_agent_control ← runtime enforcement
│       eval_config.py    build_eval_config / write_eval_config ← manifest → eval config
```

`__init__.py` loads Layer-2 symbols **lazily** (PEP 562 `__getattr__`): the pure
helpers (`findings`, `prompt_builder`, `eval_config`) import with no extra, while
`generate` (needs `acs-generator`) and `validate`/`guard` (need
`agent-control-specification`) only import when actually called — and raise a clear
`pip install "assert-ai[acs]"` hint if the AGT package is missing.

### 8.3 Command → code map

What each CLI command actually invokes, end to end:

| CLI command | CLI wrapper (`cli.py`) | ASSERT adapter fn | Delegates to (AGT) |
| --- | --- | --- | --- |
| `assert-ai acs generate` | `acs_generate` :1402 | `findings.load_findings` → `prompt_builder.build_guardrail_prompt` → `generate.generate_policy` | `acs_generator.GenerationEngine.generate` |
| `assert-ai acs validate` | `acs_validate` :1488 | `findings.load_findings` → `validate.validate_policy` | `agent_control_specification.NativeRuntimeClient.evaluate_intervention_point` |
| `assert-ai acs eval-config` | `acs_eval_config` :1537 | `eval_config.write_eval_config` | (none — pure ASSERT: manifest → eval config) |
| *(runtime, no CLI)* | — | `guard.build_agent_control` / `protect_tool` (used by `agent_guarded.py`) | `agent_control_specification.AgentControl` |

### 8.4 `generate` and `validate`, traced through the layers

**`assert-ai acs generate`** — the CLI is ~30 lines of plumbing; the synthesis is
AGT's:

```python
# cli.py:1448-1461 (condensed) — Layer 1 just wires symbols together
load_findings   = _load_acs_symbol("load_findings")
generate_policy = _load_acs_symbol("generate_policy")
summary   = load_findings(resolved_run_dir, min_rate=min_rate, min_count=min_count)
artifacts = generate_policy(summary, out_dir=policy_out_dir, ...)

# integrations/acs/generate.py:90-101 — Layer 2 builds the feed, then delegates
guardrail = build_guardrail_prompt(summary, tool_schema=tool_schema)  # ASSERT
lm        = build_language_model(lm_kind, model=model)                # ASSERT
engine    = GenerationEngine(lm)                                      # ← AGT
result    = engine.generate(prompt=guardrail.prompt, out_dir=out_path,
                            tool_inventory=guardrail.tool_inventory, ...)  # ← AGT writes Rego
```

**`assert-ai acs validate`** — ASSERT replays its own known-bad examples through
AGT's runtime, then applies ASSERT-specific accounting:

```python
# integrations/acs/validate.py:198-208 — AGT runtime does the evaluation
client = NativeRuntimeClient.from_path(str(resolved))            # ← AGT
for example in examples:                                         # ASSERT's known-bad findings
    request = InterventionPointRequest(
        intervention_point=point, snapshot=dict(example.snapshot))
    result = await client.evaluate_intervention_point(request)  # ← AGT verdict
    cases.append(_build_case(example, result))                  # ASSERT accounting
```

The ASSERT-specific accounting is the interesting part: a `runtime_error:` deny or
an undeclared-point case is counted as **not handled** (`validate.py:57-67`,
`222-255`), because the deployed guard would not actually protect those — AGT
returns the verdict, ASSERT decides what it means for *this* evaluation.

### 8.5 Where to look when something breaks

| Symptom | Layer at fault | File |
| --- | --- | --- |
| `assert-ai acs` command/flag wrong, bad run-dir resolution | Layer 1 (CLI) | `cli.py:1395-1560` |
| "install `assert-ai[acs]`" hint on a command | dependency boundary | `cli.py:99` / `integrations/acs/__init__.py:133-168` |
| Findings summary empty / wrong rates fed in | ASSERT adapter | `integrations/acs/findings.py` |
| Generated Rego over/under-denies | AGT generator (prompt is ASSERT's) | `prompt_builder.py` (feed) + AGT `acs_generator/engine.py` (synthesis) |
| Every verdict `deny` / `runtime_error` | AGT runtime (OPA missing, bad manifest) | `agent_control_specification` SDK + `opa` on PATH |
| Validation says "handled" but runtime doesn't protect | ASSERT accounting | `validate.py:222-255` |

---

## 10. Six things to remember

1. **Same ruler before and after.** Baseline and governed configs differ in only
   two lines (`run:` and `target.callable`).
2. **Tool-gate failures need a callable target.** `guard_target` (input/output)
   cannot govern a tool call; wrap the tool with `control.protect_tool`.
3. **The policy is generated from structured findings, not transcripts.** Grounded
   and privacy-safe — but LLM-authored, so **read the Rego**.
4. **Guard both tool points, and keep OPA on PATH.** Otherwise it fails closed and
   fakes a great (but useless) delta.
5. **Always report `overrefusal` next to the delta.** A drop bought with
   over-denial is not a win.
6. **Native adapter only.** `assert-ai acs generate/validate` — never hand-drive an
   external `acs` CLI for this loop. Everything stays in-IDE.

---

## 11. Worked example (numbers)

1. Baseline → `policy_violation` **40%**.
2. `acs generate` → manifest + Rego guarding the four high-risk tools at
   `pre_tool_call`.
3. `acs validate` → known-bad examples strongly blocked.
4. Governed → `policy_violation` **5%**.
5. `results compare` → **40% → 5%, ACS Delta 35 points**, `overrefusal` flat. ✅
6. Export both runs → SharePoint → ledger row → `record_suggestion` back to Clarity.
