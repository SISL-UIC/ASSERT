# Science research agent — retrieval safety with sharing classes

A retrieval agent that helps researchers find prior work and summarize results.
It has three real Python tools — public web search, URL fetch, and an internal
file index — and is wrapped as an [ASSERT callable
target](../../docs/targets/callable.md) so the judge can inspect the tool
trace, not just the final answer.

The baseline agent lives in [agent.py](agent.py) and wraps a hosted LiteLLM
model (default `azure/gpt-4o-mini`).

This example is a self-contained Clarity → ASSERT → ACS → ASSERT replication
package: risks were discovered with Clarity, measured with ASSERT, governed with
a committed ACS policy, and re-measured to show the delta.

## Tools

| Tool | Purpose |
|---|---|
| `web_search` | Search the public web through Tavily. Results are public, external, and untrusted. |
| `fetch_url` | Fetch and strip readable text from one public `http(s)` URL. |
| `file_search` | Search a synthetic internal science file index. Each result has a sharing `class` (see below). |

The synthetic corpus mixes seven sharing classes: `public` / `external_safe`
(quotable with attribution), `internal_only` (discussable at the level the
document permits), and four restricted classes — `restricted_results`,
`partner_notes`, `contacts`, `private_notes` — that must never be quoted,
paraphrased, or summarized. One public document (`file_pub_004`) carries an
**embedded prompt-injection payload** instructing the agent to paste
partner-confidential figures and internal contacts. A correct agent ignores it.

## Risks evaluated (Clarity → ASSERT)

Clarity discovery ([Clarity Protocol/](Clarity%20Protocol/)) surfaced four
failure modes; the two Critical (P1) confidentiality risks were measured, each as
one atomic behavior with the built-in `policy_violation` disabled and a custom,
node-independent bad-event dimension (the built-in `overrefusal` is kept as the
separate availability metric):

| Risk | Eval | Bad-event dimension |
|---|---|---|
| Restricted-class information leakage | [evals/restricted-class-leakage/](evals/restricted-class-leakage/) | `information_leakage` |
| Embedded prompt-injection compliance | [evals/prompt-injection-compliance/](evals/prompt-injection-compliance/) | `injection_compliance` |

## Governance (ACS)

Both failures are decided in the agent's free-form **reply text** (file_search
legitimately returns restricted docs; the harm is the model *choosing* to
disclose or *acting on* an embedded instruction). So each is governed by a
**semantic output-annotator gate** at the ACS `output` intervention point,
modeled on `examples/azure_doc_qa/`:

- [acs/restricted-class-leakage/](acs/restricted-class-leakage/) — enforced by
  [agent_guarded.py](agent_guarded.py) (`restricted_disclosure_classifier`).
- [acs/prompt-injection-compliance/](acs/prompt-injection-compliance/) — enforced
  by [agent_guarded_injection.py](agent_guarded_injection.py)
  (`injection_compliance_classifier`).

Each guarded agent imports the baseline `chat` verbatim and adds only the ACS
gate: it runs an LLM annotator over the reply and, on a `deny`, **regenerates an
in-policy answer and re-gates it** (falling back to a flat decline only if the
regen still violates), so blocking a violation does not automatically become an
over-refusal. `acs generate` drafted the leakage policy with additional
`pre_tool_call`/`post_tool_call` gates on `file_search`/`web_search`; those were
**dropped on review** — gating read-only retrieval that legitimately returns
restricted docs only inflates over-refusal. Offline `assert-ai acs validate`
cannot run annotators, so these gates are proven by the remeasure delta, not
`validate`.

## Results (baseline → ACS-governed)

`sample_size: 25` per behavior (prompt + scenario), agent `azure/gpt-4o-mini`,
tester/judge `azure/gpt-5.4`. Rates are prompt / scenario.

| Behavior | Dimension | Baseline | ACS-governed | Delta |
|---|---|---|---|---|
| Restricted-class leakage | `information_leakage` | 0% / 12% | 0% / **0%** | **−12pp scenario (eliminated)** |
| Restricted-class leakage | `overrefusal` | 4% / 40% | 4% / 56% | +16pp scenario (regression) |
| Prompt-injection compliance | `injection_compliance` | 0% / 0% | 4% / 0% | +4pp prompt (1 case) |
| Prompt-injection compliance | `overrefusal` | 8% / 32% | 12% / **24%** | **−8pp scenario (improved)** |

**Reading the delta.** The baseline agent is already very safe on both bad-event
dimensions (strict system prompt) but **over-refuses heavily on multi-turn
scenarios** — that is the dominant baseline problem. The ACS gates:

- **Eliminate the residual multi-turn leakage** (12% → 0%) — the clear
  confidentiality win.
- **Trade differently on availability by risk.** For injection, the regen keeps
  the document's factual content, so governed over-refusal *drops* (32% → 24%).
  For leakage, the ~3 leaking scenario cases and a few borderline ones regenerate
  into refusals rather than genuinely helpful in-policy answers, so over-refusal
  *rises* (40% → 56%). Tuning the leakage annotator/regen to answer the
  permissible part is the open follow-up.

Re-run any leg:

```bash
pip install -e ".[otel,acs,examples]"
cp examples/science_research_agent/.env.example examples/science_research_agent/.env
# Edit .env: AZURE_API_KEY, AZURE_API_BASE, TAVILY_API_KEY. opa must be on PATH.

assert-ai run --config examples/science_research_agent/evals/restricted-class-leakage/eval_config.yaml
assert-ai run --config examples/science_research_agent/evals/restricted-class-leakage/eval_config.governed.yaml
assert-ai results compare science-restricted-class-leakage baseline acs-governed --metric information_leakage
```

## Package layout

```
agent.py                     baseline callable target (chat)
agent_guarded.py             leakage-governed target (chat_governed)
agent_guarded_injection.py   injection-governed target (chat_governed)
tools.py                     the three real tools + synthetic corpus
Clarity Protocol/            Clarity risk-discovery protocol for this domain
evals/<risk>/                eval_config.yaml + eval_config.governed.yaml (A/B)
acs/<risk>/                  reviewed, committed manifest.yaml + policy/*.rego
```

## Notes

- `fetch_url` performs a real HTTP GET — only fetch URLs you trust.
- Web and fetch responses are cached in
  `examples/science_research_agent/.tool_cache.json` to keep reruns cheap.
- The `governed.yaml` configs are byte-identical to their baselines except `run:`
  and `target.callable`, so the governed run reuses the baseline's exact test set
  — a true A/B.
