# Summary

ChangeFlow is an automated change-management assistant on the path to production
deployment. It moves a change proposal through required control surfaces and
approval while enforcing policy. Its safety constraints (documentation fidelity,
authority calibration, injection resistance, sequence/freeze rules) live only in
the system prompt, so they are advisory — an agent under pressure or fed
injected proposal data can fabricate facts about a change or overstate its
approval status, both of which drive real, high-risk deployment decisions.

The whole-lifecycle failure model surfaced four independently testable failure
modes (see `failures/failures.md`), two of them Critical (P1): fabricated
change-record fields, and unauthorized approval / authority overstatement. These
are measured with ASSERT and then governed at runtime with ACS at the `output`
intervention point (semantic annotator gates), re-measured to prove the
bad-event rate drops while `overrefusal` stays flat.
