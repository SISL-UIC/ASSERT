# Architecture

## Shape

A single-turn, tool-less **prompt agent** implemented as a Python callable
(`examples/career_health_assessment/agent.py:chat`). One `litellm.completion` call
against an Azure OpenAI deployment (`azure/gpt-4o-mini` by default, temperature
1.0), seeded with a fixed `SYSTEM_PROMPT` plus the untrusted user turn. Returns the
model's raw JSON string. No tools, no retrieval, no memory — the system prompt IS
the agent.

## Trust boundary

```mermaid
flowchart LR
    user[User / caller] -->|TASK + CV_TEXT + fields\n(UNTRUSTED)| agent[career_health chat callable]
    sys[SYSTEM_PROMPT\n(trusted contract)] --> agent
    agent -->|litellm.completion| model[(Azure OpenAI\ngpt-4o-mini)]
    model --> agent
    agent -->|structured JSON reply| user

    subgraph Threats
        t1[T1 Fabrication / inference\nof unstated facts & scores]
        t2[T2 Prompt injection via CV_TEXT\ninstructions followed / rewarded]
        t3[T3 Unbounded readiness /\npersonality claims]
        t4[T4 Hidden prompt / policy\ndisclosure]
        t5[T5 Human / credential\nmisrepresentation]
    end
    agent -.governed at.-> gate[ACS output gate\n(semantic annotator)]
```

The only trust boundary is **user-supplied text vs. the system prompt**. Because
there are no tools, every failure surfaces in the **assistant's free-form JSON
reply** — so the governable enforcement point is the ACS `output` intervention
point with an LLM annotator (govern-and-remeasure Shape 4), not a tool gate.

## Governed variant

`agent_guarded.py` imports `chat` / `SYSTEM_PROMPT` from `agent.py` and adds only
an ACS output gate: after the baseline reply is produced, an LLM annotator judges
it against the specific failure class; on `deny` the agent regenerates a
bounded/grounded reply and re-gates it, so blocking a violation does not become an
overrefusal. The A/B differs by nothing but the gate.

## Threat model

See `.clarity-protocol/threat-model.md` for the ranked summary. Top risks:
fabrication/inference (T1) and prompt injection (T2) are the highest-severity,
most-elicitable failures; readiness/personality overreach (T3) and prompt/policy
disclosure (T4) follow.
