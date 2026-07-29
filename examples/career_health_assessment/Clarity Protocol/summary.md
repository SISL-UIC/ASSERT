# Summary

The **career health assessment agent** is a bounded, tool-less prompt agent that
turns synthetic CV text into structured JSON for one of three tasks (`cv_parsing`,
`narrative_assessment`, `cv_quality_evaluation`). Its whole value is a promise of
restraint: assert only what an exact span of `CV_TEXT` supports, and treat all
user input as untrusted data. Two Critical failure modes break that promise —
**fabricating / inferring unsupported facts and scores** (evidence-grounding) and
**obeying instructions embedded in CV_TEXT** (input isolation) — plus two High
modes (narrative overreach, prompt disclosure). Because there are no tools, every
failure lands in the free-form reply, so governance is a semantic `output`
annotator gate, proven via an ASSERT baseline → ACS → re-measure A/B. The top two
P1 Criticals are carried forward for measurement.
