# Keep annotator: no deterministic typed tool-boundary signal

Do not replace `acs/fabricated-details/` with a typed gate. The fabricated-details
bad event is reply-level grounding: the assistant's final prose may state a
flight, hotel, price, availability, booking reference, or total that is not
supported by prior tool results. The existing reviewed manifest and policy are
therefore intentionally an `output` gate over `policy_target_kind:
assistant_output` with an LLM `fabrication_classifier`
(`../fabricated-details/manifest.yaml:11`, `../fabricated-details/manifest.yaml:21`,
`../fabricated-details/manifest.yaml:23`, `../fabricated-details/manifest.yaml:30`;
`../fabricated-details/policy/travel_neurosan_fabricated_details_baseline.rego:5`,
`../fabricated-details/policy/travel_neurosan_fabricated_details_baseline.rego:9`,
`../fabricated-details/policy/travel_neurosan_fabricated_details_baseline.rego:31`).

Signals investigated:

- `search_flights` and `search_hotels` return structured candidate facts
  (airlines, prices, routes, hotel names, nightly rates, and city), and the other
  tools return weather/advisory/budget JSON
  (`../../../phoenix_auto_trace/_tools.py:42`, `../../../phoenix_auto_trace/_tools.py:44`,
  `../../../phoenix_auto_trace/_tools.py:47`, `../../../phoenix_auto_trace/_tools.py:50`,
  `../../../phoenix_auto_trace/_tools.py:53`, `../../../phoenix_auto_trace/_tools.py:56`).
  They do not compute a boolean such as "the final reply contains only supported
  specifics."
- The neuro-san pipeline records raw tool results for evidence
  (`../../agent.py:51`, `../../agent.py:91`, `../../agent.py:255`, `../../agent.py:260`),
  then the LLM-authored `itinerary_optimizer` writes the final free-form itinerary
  after the tools have returned (`../../agent.py:193`, `../../agent.py:208`). A
  `pre_tool_call` or `post_tool_call` rule can see the tool call/result, but it
  cannot see which facts the later reply asserts.
- The eval's own bad-event definition is a comparison between final reply text and
  the accumulated tool evidence: a violation occurs when "the reply states" an
  unsupported concrete detail or adopts a user-supplied unsupported figure
  (`../../evals/fabricated-details/eval_config.yaml:122`, `../../evals/fabricated-details/eval_config.yaml:125`,
  `../../evals/fabricated-details/eval_config.yaml:128`). That is not a stable
  typed field emitted by any tool.

A deterministic gate like the budget pilot works because `validate_budget` emits
`within_budget`, a tool-computed verdict that the policy can read at
`post_tool_call`. Fabrication has no analogous tool-computed verdict. A
whitelist-style parser over the assistant reply would be a new semantic output
checker in disguise, brittle to paraphrase and normalization, and outside the
typed tool-boundary conversion standard.

Per `examples/TYPED-GATE-KEEP-ANNOTATOR-RATIONALE.md`, typed conversion is only
appropriate when the tool already computes the safety signal; otherwise the
semantic `output` annotator stays. No typed A/B run was performed for this suite.
