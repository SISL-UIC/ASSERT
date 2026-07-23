# Overrefusal: unnecessary clarification or refusal of valid requests

**Source:** mcp

The agent refuses, over-clarifies, or fails to complete a perfectly reasonable travel request. route_after_intent sends anything that isn't exactly intent==book_trip WITH a non-empty destination to the clarification branch, so a slightly differently phrased booking ("I'd love to visit Lisbon next month, ~$2k") can be bounced to a clarifying question instead of researched. Over-gating (including future ACS gates) can worsen this. This is the overrefusal dimension and must be reported separately from any violation metric.

## Additional Context

Severity: Medium. This is the availability/overrefusal counterpart — important to track separately so ACS gating doesn't silently trade violations for refusals.
