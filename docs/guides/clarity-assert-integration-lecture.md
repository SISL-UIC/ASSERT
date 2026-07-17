# Lecture Notes: How Clarity Integrates with the ASSERT Skill

> **One-sentence thesis:** Clarity **discovers** *which* risks your AI system has;
> ASSERT **measures** *how often* each one actually fires. The two are glued together
> by (a) a set of **files** on disk (`.clarity-protocol/`) and (b) one small,
> deterministic **parser** (`clarity_intake.py`). Everything else is *instructions*
> that a coding agent (Copilot / Claude / Cursor) follows.

---

## 0. The mental model (read this first)

Three distinct actors, and it's easy to conflate them:

| Actor | What it is | Role in this story |
| --- | --- | --- |
| **Clarity** | A Python risk-discovery agent (`microsoft/clarity-agent`) that ships an **MCP server** | The **server** — exposes 9 tools; produces failure docs |
| **The coding agent** | Copilot / Claude / Cursor in your IDE | The **MCP client** *and* the reader of the skill instructions — it drives everything |
| **ASSERT** | A behavior-eval framework (`responsibleai/ASSERT`) driven by `eval_config.yaml` | The **measurement engine** — turns a config into violation rates |

The single most important idea:

```
The "skill" is NOT a program. It is a set of Markdown instructions the coding
agent reads and follows. The only real *code* in the whole integration is
clarity_intake.py (a file parser). Clarity and ASSERT are the two engines;
the agent is the conductor holding the sheet music (the skill).
```

---

## 1. The big picture — one diagram

```
+------------------------------------------------------------------------------+
|                     YOUR IDE (Copilot / Claude / Cursor)                     |
|                                                                              |
|  +----------------------------+            +------------------------------+  |
|  | THE CODING AGENT           |   reads    | THE SKILL (docs)             |  |
|  | (the MCP *client*)         |instructions| SKILL.md / .prompt           |  |
|  |                            |<---------- | * .md / .mdc +               |  |
|  |                            |            | * workflows/*.md             |  |
|  |                            |            |                              |  |
|  +----------------------------+            +------------------------------+  |
|                                                                              |
|  (A) MCP tool calls                        (C) shell / file ops              |
|                                                                              |
+------------------------------------------------------------------------------+
                 |                                          |
                 v                                          v
   +--------------------------------+       +----------------------------------+
   | CLARITY MCP SERVER             |       | FILES ON DISK (the handoff)      |
   | (clarity-agent)                |       |                                  |
   | 9 tools:                       |       |   .clarity-protocol/             |
   |   run_clarity                  |--->   |     failures/failures.md         |
   |   write_protocol_document      |       |     failures/failure-NN-*.md     |
   |   record_failure ...           |       |     summary.md, goal/, solution/ |
   +--------------------------------+       +----------------------------------+
                                                             |
                                            (B) python clarity_intake.py
                                                             |
                                                             v
                                            +----------------------------------+
                                            | candidate behaviors (in memory)  |
                                            | {name, description, severity,    |
                                            |  priority, dimensions, ...}      |
                                            +----------------------------------+
                                                             | (triage gate)
                                                             v
                                            +----------------------------------+
                                            | evals/<slug>/eval_config.yaml    |
                                            +----------------------------------+
                                                             | assert-ai run
                                                             v
                                            +----------------------------------+
                                            | ASSERT pipeline: violation rates |
                                            +----------------------------------+
```

**The three connection points labeled above:**
- **(A) MCP** — the agent calls Clarity's tools over the MCP protocol (stdio).
- **(B) Parser** — pure Python reads the files Clarity wrote; never touches MCP.
- **(C) Files** — the actual handoff surface between the two systems.

Notice: **Clarity and ASSERT never talk to each other directly.** They communicate
only through the `.clarity-protocol/` files, with the agent + parser in between.
This loose coupling is the whole design.

---

## 2. What is MCP, and why is it here?

**MCP (Model Context Protocol)** is a standard way for a host agent to call external
"tools." Clarity implements an MCP **server** (`python -m clarity_agent.mcp`,
FastMCP over stdio). Your coding agent is the MCP **client**.

```
   Coding agent  ──"call run_clarity"──▶  Clarity MCP server
   (client)      ◀──"here's the guide"──  (server, stdio)
```

Wiring is done once with `clarity embed .`, which writes `.vscode/mcp.json`:

```jsonc
// .vscode/mcp.json  (this repo uses the uv-managed form)
{
  "servers": {
    "clarity-agent": {
      "command": "uv",
      "args": ["run", "--extra", "mcp", "--directory",
               "C:/Users/t-alexngo/AppData/Local/clarity-agent",
               "python", "-m", "clarity_agent.mcp",
               "--project-dir", "${workspaceFolder}"]
    }
  }
}
```

After a reload, the 9 Clarity tools appear to the agent. **The old approach shelled
out to a `clarity cli` binary — we deleted that.** Everything now goes through MCP.

### The 9 tools (you mostly use 4)

| Tool | Used when |
| --- | --- |
| `run_clarity` | **Start discovery.** Returns Clarity's real process guide inlined as text |
| `write_protocol_document` | Persist what the clarifying conversation learned |
| `record_failure` | Save a discovered failure mode into `.clarity-protocol/` |
| `record_suggestion` / `record_decision` | **Close the loop** — write the measured baseline back |
| `read_protocol_document`, `get_packet_status`, `check_decision`, `generate_packet` | Housekeeping / status |

---

## 3. Discovery is *agent-driven*, not scripted (the subtle part)

A common misconception: "`run_clarity` asks the user the questions." **It does not.**

```
   agent → run_clarity()
            └── returns: "Here is the process guide. Ask the user about
                          their system's goal, users, high-risk actions..."
   agent → (reads that guide, then asks YOU the questions in chat)
   you   → answer in plain English
   agent → write_protocol_document(...)   # persists your answers
   agent → record_failure(...)            # for each risk it distills
   ...repeat until failures/failures.md exists...
```

So **the agent is the interviewer**; Clarity supplies the *interview script* and the
*filing cabinet*. This is why the skill says "do not imitate Clarity's questioning
from your own head" — you must let `run_clarity` hand you the real guide, then follow
it. The result is a populated `.clarity-protocol/` directory.

```
.clarity-protocol/
├── summary.md                     ← one-paragraph system description
├── goal/requirements.md           ← what the system must/mustn't do
├── solution/architecture.md       ← how it's built
└── failures/
    ├── failures.md                ← INDEX of all failure modes
    ├── failure-01-user-disengagement.md
    ├── failure-07-operational-risks.md
    └── ...
```

---

## 4. The handoff files — anatomy of a failure doc

This is what the parser reads. Two shapes:

### 4a. `failures.md` — the index

```markdown
# Failure Modes
7 failure modes identified across the agent lifecycle.

## Managed
1. **[User Disengagement](failure-01-user-disengagement.md)** (High) The user
   stops trusting the assistant after... Managed with ...
2. **[Operational and Security Risks](failure-07-operational-risks.md)**
   (Medium–Critical) Cost overruns and prompt injection... Managed with ...
```

The parser pulls: **title, relative doc path, severity, summary**. Note the
`Medium–Critical` **en-dash range** → it keeps the **max** (Critical).

### 4b. `failure-NN-*.md` — one doc per failure

```markdown
# Failure: User Disengagement

## Summary
<prose>  ←── becomes behavior.description (tightened to a testable statement)

## Failure Chain
1. User arrives with a challenging disposition
   *Intervention point (detection)*   ←── structural NOISE, filtered out
   *Branch (...)*                       ←── structural NOISE, filtered out
2. Assistant mis-calibrates tone
   *Observation: ...*                   ←── structural NOISE, filtered out
   ↑ the *conditions* here → interaction_condition dimension

## Observations
**Severity:** High — <rationale>       ←── severity + priority
**Variants:**                          ←── THE HIGHEST-VALUE SIGNAL
- challenging disposition
- wrong calibration
- happy-path attachment
- ... (7 total)                        ←── each variant = one elicitation route
                                            → elicitation_variant dimension

## Intervention Points
prevention / detection / mitigation    ←── kept for the report's "a fix would target"
```

---

## 5. `clarity_intake.py` — the deterministic glue

This is the **only real code**. It reads the files above and emits structured
**candidate behaviors**. It never touches MCP, never runs ASSERT.

```
        failures/*.md   -->   clarity_intake.py   -->   [CandidateBehavior, ...]
                         |
                         v
      +------------------------------------------------------------------------+
      | * normalize_severity        (Critical/High/Medium/Low,                 |
      |                              ranges -> max, unknown -> Unknown)        |
      | * severity_to_priority      (Crit->P1  High->P2  Med->P3  Low->P4)     |
      | * parse_failures_index      (the index list)                           |
      | * _extract_variants         (Variants -> elicitation_variant)          |
      | * _extract_chain_conditions (Chain -> interaction_cond,                |
      |                              filters _CHAIN_NOISE)                     |
      | * derive_dimensions         (assemble stratify dimensions)             |
      | * _detect_bundle            (multi_behavior + splits)                  |
      | * parse_failure_doc / build_candidate_behaviors                        |
      +------------------------------------------------------------------------+
```

Each candidate looks like:

```python
CandidateBehavior(
  name="user_disengagement",
  description="<from Summary, tightened>",
  severity="High",
  priority="P2",
  source_doc="failures/failure-01-user-disengagement.md",
  candidate_dimensions=[
     {"name": "elicitation_variant",
      "description": "Values: challenging disposition; wrong calibration; ..."},
     {"name": "interaction_condition",
      "description": "Values: embedded vs direct; verbose vs terse; ..."},
  ],
  multi_behavior=False,
  suggested_splits=[],
  warnings=[],
)
```

**Two design principles baked in:**
1. **Tolerant parsing** — unknown severities, missing headers → the candidate arrives
   *flagged* (`warnings` populated), never crashes, never silently drops a failure.
2. **Bundle detection** — if one doc mixes several independently-testable behaviors
   (e.g. failure-07 "operational **and** security"), it sets `multi_behavior=True`
   and proposes `suggested_splits` so the atomicity rule is preserved.

Covered by **21 pytest cases** against real Clarity fixtures + synthetic
malformed-input fixtures.

---

## 6. The measurement workflow — 8 steps

This is `workflows/measure-clarity-failures.md`. The three skill surfaces stay
high-level and *delegate* to this doc (the "one source of truth" we discussed).

```
 Step 0  Entry: user asks to "measure/test/quantify" risks
           │
           ├─ failures.md exists? ──▶ Step 1
           └─ no? ──▶ run_clarity discovery first (Section 3), then Step 1
           ▼
 Step 1  PARSE       python clarity_intake.py .clarity-protocol
           ▼                → candidate behaviors (disposable cache)
 Step 2  TRIAGE GATE ★ MANDATORY HUMAN DECISION ★
           │  Present candidates sorted P1→P3, show splits + warnings.
           │  "P1s only" is the default. NOTHING is generated/run until
           │  the user answers. Declining ⇒ zero files, zero runs.
           ▼
 Step 3  GENERATE    one atomic evals/<slug>/eval_config.yaml per pick
           │          (domain template first, else assert-ai init --describe)
           │          fold Variants → stratify.dimensions, sample_size=10
           ▼
 Step 4  ATOMICITY   N behaviors ⇒ N configs. NEVER bundle.
           ▼
 Step 5  CONFIRM ★   show behavior/dimensions/target/judge; run only on go-ahead
           ▼
 Step 6  RUN         assert-ai run --config evals/<slug>/eval_config.yaml
           │          sequential; one failing run doesn't stop the rest
           ▼
 Step 7  REPORT      one behavior/column, one experiment/row;
           │          policy_violation AND overrefusal reported SEPARATELY;
           │          cite examples from scores.jsonl; note "a fix would target..."
           ▼
 Step 8  CLOSE LOOP  record_suggestion back into .clarity-protocol/:
                      "this failure mode now has a measured baseline at evals/<slug>/"
```

★ = a mandatory **human gate**. The system intentionally over-produces risks, so
auto-running everything is treated as a bug, not a feature.

---

## 7. Why the mapping matters (Clarity concept → ASSERT concept)

The value of the integration is that Clarity's *structure* maps cleanly onto
ASSERT's *config schema*:

| Clarity produces | Maps to ASSERT | Why it's high-signal |
| --- | --- | --- |
| A **failure mode** | one atomic `behavior` | keeps `policy_violation` a clean yes/no |
| Failure **Summary** | `behavior.description` | a real, human-vetted risk statement |
| **Variants** list | `elicitation_variant` stratify dimension | each variant = a distinct way to *trigger* the failure → the test set samples across real attack/elicitation routes instead of random prompts |
| **Failure Chain** conditions | `interaction_condition` dimension | the *situations* where it manifests |
| **Severity** | priority (P1–P4) | drives triage ordering |
| `summary.md` / `goal/` / `solution/` | `context` | grounds the judge in the real system |
| **Intervention Points** | report's "a fix would target…" | connects measurement back to a remedy |

Without Clarity, you'd hand ASSERT a plain-language guess → low-signal eval. With
Clarity, every dimension is grounded in a real, structured threat model.

---

## 8. Where the AI Red Teaming angle fits (your earlier idea)

The same handoff shape generalizes: a red-teaming run's **finding** describes *how*
a failure was elicited. That "how" is exactly what `elicitation_variant` captures.
So a red-team finding can be recorded (`record_failure`) into `.clarity-protocol/`
alongside Clarity's own risks, and the *identical* parser → triage → config →
measure loop then quantifies how often that finding reproduces. Clarity's risk list
and red-team findings become **two sources feeding one measurement pipeline.**

---

## 9. Design invariants (the "rules of the game")

1. **Loose coupling via files.** Clarity ↔ ASSERT communicate only through
   `.clarity-protocol/`. Neither imports the other.
2. **The skill is instructions; only `clarity_intake.py` is code.**
3. **`.clarity-protocol/` is the source of truth.** The parser's JSON is a
   *disposable cache* — never authoritative, never committed as such.
4. **One atomic behavior per config.** Bundling hides per-behavior signal.
5. **Two mandatory human gates** — triage (Step 2) and pre-run confirmation (Step 5).
6. **Don't modify clarity-agent source.** Consume its MCP server as shipped.
7. **`policy_violation` and `overrefusal` are separate problems** — always reported
   separately (a system can under-refuse *and* over-refuse at once).
8. **Runtime output is gitignored** in the framework repo (`.clarity-protocol/`,
   `evals/`) because it describes a system-under-test, not ASSERT itself. Adopters
   using the skill in their *own* product repo commit the durable docs instead.
9. **Credentials by NAME only** — never read/print/commit `.env` or `artifacts/`.

---

## 10. End-to-end trace (the worked example)

```
You:  "Help me evaluate a SaaS customer-support chatbot for a B2B billing product..."
        │
Agent:  run_clarity() → gets guide → interviews you in chat about the bot
        write_protocol_document(...) ; record_failure(...) × several
        → .clarity-protocol/failures/failures.md now exists
        │
Agent:  python clarity_intake.py .clarity-protocol
        → candidates: user_disengagement (P1), cross-tenant-data-exposure (P1),
          identity-verification-bypass (P1), operational-risks (P3, multi_behavior)...
        │
Agent:  [TRIAGE] "Here are the candidates P1→P3. Measure P1s only? Named picks?"
You:    "P1s only."
        │
Agent:  generates evals/user-disengagement/eval_config.yaml (+ the other P1s),
        each with an elicitation_variant dimension, sample_size: 10
        [CONFIRM] shows you each config
You:    "go"
        │
Agent:  assert-ai run --config evals/user-disengagement/eval_config.yaml  (then next)
        → results table: user_disengagement → policy_violation X%, overrefusal Y%,
          3–5 cited failing cases
        │
Agent:  [CLOSE LOOP] record_suggestion: "user_disengagement now has a measured
        baseline at evals/user-disengagement/."
```

---

## Glossary

- **MCP** — Model Context Protocol; how the agent calls Clarity's tools.
- **`.clarity-protocol/`** — the directory Clarity writes; the handoff surface.
- **Candidate behavior** — parser output; a proto-`eval_config.yaml`.
- **Stratify dimension** — an axis the test set samples across (e.g. variant, condition).
- **Triage gate** — the mandatory human "which risks now?" decision.
- **`policy_violation` / `overrefusal`** — the two ASSERT judge dimensions, always separate.
- **Close the loop** — writing the measured baseline back into Clarity via `record_suggestion`.
