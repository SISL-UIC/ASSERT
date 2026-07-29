# baseline+governed measured

**Source:** mcp
**Target:** failures/failures.md

failure-01 (tool-laundered dosage) and failure-02 (unsafe interaction clearance / profile diagnosis) were converted into ASSERT suites and measured. Baseline harm_actionability: dosage prompt 16% / scenario 76%; interaction prompt 60% / scenario 96%. After the ACS semantic OUTPUT annotator gate (agent_guarded:chat_governed): dosage prompt 4% / scenario 36%; interaction prompt 4% / scenario 44%. Evals live at examples/prompt_agents/sim_tools/evals/{dosage,interaction}; gate at acs/harmful_medical_advice + agent_guarded.py. Overrefusal rose on scenarios (dosage +16pp, interaction +40pp) as the precision trade-off.

## Rationale

Closes the Clarity loop: records that the top-2 P1 risks were governed and remeasured with a proven delta, and where the reproducible artifacts live.
