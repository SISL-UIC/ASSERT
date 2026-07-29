# Restricted-disclosure: typed tool-boundary gate vs. semantic output annotator (A/B)

Proof-of-concept converting the science `restricted-disclosure` governance from a
semantic `output` annotator gate (`../restricted-disclosure/`, conditioned on
`restricted_disclosure_classifier`) to a deterministic typed `post_tool_call`
gate that reads `file_search` result classes.

## Why this is possible

`file_search` returns `results[*].class`. The restricted set is
`{restricted_results, partner_notes, contacts, private_notes}`. The typed Rego
flags only `file_search` results containing those classes; the host runtime then
performs deterministic remediation.

## Mixed-result handling

The policy denies/flags restricted presence at `post_tool_call`; the runtime owns
remediation because it can safely rewrite the tool result before the model sees
it. Mixed results are filtered to public/permitted entries and returned to the
model. If all results are restricted, the runtime returns a content-free policy
block pointing to the access-request channel.

A final deterministic evidence fallback is used when the model tries to infer or
compare against omitted material after filtering: it answers only from the
approved result entries. This reduced leakage but still caused some availability
cost on requests whose ideal answer required bespoke public-only wording.

## Files

| File | Role |
|---|---|
| `policy/restricted_disclosure_typed.rego` | Deterministic post-tool gate on `file_search` result classes. |
| `manifest.yaml` | Declares `pre_tool_call` default allow and `post_tool_call` on `file_search`; no annotators. |
| `../../agent_guarded_disclosure_typed.py` | Runtime enforcement with deterministic mixed-result filtering. |
| `../../evals/restricted-disclosure/eval_config.typed.yaml` | Governed typed config using `run: acs-governed-typed`. |

## A/B results (sample_size 25 prompt + 25 scenario; judge azure/gpt-5.4)

| Run | prompt `restricted_class_disclosure` | scenario `restricted_class_disclosure` | prompt `overrefusal` | scenario `overrefusal` |
|---|---:|---:|---:|---:|
| baseline (ungoverned) | 24% | 56% | 40% | 36% |
| annotator `output` gate | 8% | 8% | 36% | 64% |
| **typed `post_tool_call` gate** | **0%** | **8%** | 44% | 56% |

**Headline:** the typed gate matches the annotator's scenario bad-event rate and
improves prompt bad-event rate to 0%, while reducing the annotator's scenario
overrefusal tax (56% vs 64%). It did **not** keep overrefusal at/below baseline:
prompt is +4pp and scenario is +20pp vs baseline, mostly on cases where filtering
removed restricted context and the final deterministic permitted-only answer was
scored as insufficiently tailored.

## Overrefusal decomposition (baseline false -> typed true)

| Slice | flips | ACS filtered | ACS full block | no ACS intervention |
|---|---:|---:|---:|---:|
| prompt | 6 | 4 | 0 | 2 |
| scenario | 10 | 8 | 0 | 2 |

Most new typed overrefusals are filter-caused, not runtime variance; none came
from full all-restricted blocks. The remaining no-intervention flips are baseline
agent stochasticity / tester path variance.

## Offline validation

- `opa eval`: mixed result (`public` + `partner_notes`) -> deny reason
  `restricted_class_file_search_result`; public/external-safe result -> allow.
- `protect_tool` smoke: public -> allow; mixed -> ACS deny followed by runtime
  public-only filtered payload; all-restricted -> ACS deny followed by content-free
  block.

## Reproduce

```powershell
& "C:\Users\t-alexngo\AppData\Local\Programs\Python\Python312-arm64\Scripts\assert-ai.exe" run --config examples\science_research_agent\evals\restricted-disclosure\eval_config.typed.yaml --force-stage inference
```
