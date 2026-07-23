# Fabricated details: ACS output-annotator governed delta

**Source:** mcp
**Target:** failures/failures.md

failure-02 (Fabricated details) now has an ACS output-annotator governed re-measure. A committed semantic gate at the ACS output intervention point (examples/travel_planner_langgraph/acs/fabricated-details/), enforced by a runtime LLM grounding annotator in agent_guarded_output.py, cut fabricated_details from 36% to 8% prompt (down 28pp) and 76% to 24% scenario (down 52pp); the worst category "Fully invented bundled itinerary" fell 100% to 20% (down 80pp). Cost: scenario overrefusal rose 24% to 68% because the fixed block-fallback flatly refuses even legitimate high-level help (trip structure, neighborhoods). Follow-up: replace the blunt fallback with a grounded high-level plan that states uncertainty and offers to pull real options, recovering overrefusal while keeping the fabrication block; and tighten the annotator to catch residual cases (weather/advisory/total specifics). Eval: examples/travel_planner_langgraph/evals/fabricated-details/eval_config.governed.yaml.

## Rationale

Records the governed A/B for failure-02 (semantic output-annotator gate) so Clarity knows the risk now has both a baseline and a proven runtime control, plus the overrefusal tradeoff to address next.
