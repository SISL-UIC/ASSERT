# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Reference callable travel-planning agent for the govern-and-remeasure loop.

``agent`` is the ungoverned LangGraph baseline (its grounding / budget /
advisory promises live only in the system prompt). ``agent_guarded`` is the same
agent re-run with an ACS ``output`` annotator gate that judges the final reply
and regenerates a grounded, in-budget answer on a violation, so ASSERT can
measure the failure-rate delta between the two.
"""
