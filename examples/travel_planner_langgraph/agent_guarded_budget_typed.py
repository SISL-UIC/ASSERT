# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""PROOF-OF-CONCEPT — budget-overrun governed by a DETERMINISTIC tool-boundary
gate instead of a semantic ``output`` annotator.

Contrast with :mod:`examples.travel_planner_langgraph.agent_guarded`
(``chat_governed``), which routes the agent's final PROSE through an ACS
``output`` point conditioned on an LLM annotator (``budget_overrun_classifier``).
That design is the source of the measured overrefusal rise: the classifier can
mis-flag an in-budget reply, and every ``deny`` throws the whole answer away and
regenerates / falls back to a blanket abstention.

This module governs the SAME failure with the typed policy in
``acs/budget-overrun-typed/`` (see ``travel_budget_overrun_typed.rego``). The
``validate_budget`` tool already COMPUTES ``within_budget`` from ``total <=
budget``; the gate reads that typed bool at ``post_tool_call`` via the real ACS
SDK (``control.protect_tool``), exactly like
``examples.billing_support_agent.agent_guarded``. Consequences:

* **No overrefusal by construction** — the gate fires IFF the tool computed
  ``within_budget == false``. An in-budget plan can never be flagged, so the
  common (benign) case is returned unchanged.
* **Deterministic remediation** — on a block we know the exact overage numbers,
  so we regenerate a reply that states the grounded total and clearly flags the
  overage. No LLM annotator judges the prose; no blanket "confirm your dates"
  fallback.
* **Offline-validatable** — the same policy is exercised by ``opa eval`` /
  ``assert-ai acs validate`` with no annotator runtime (the ``output`` gate shows
  "handled 0/N" offline).

Prerequisites: ``pip install -e ".[acs]"`` and ``opa`` on PATH. Provider creds in
the repo-root ``.env`` (reference names only: ``AZURE_API_KEY``,
``AZURE_API_BASE``).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import litellm

# gpt-5.x regen models reject temperature=0; drop unsupported params rather than
# hard-erroring. (No annotator here — this gate is purely typed.)
litellm.drop_params = True

from examples.travel_planner_langgraph.agent import _DEPLOYMENT
from examples.travel_planner_langgraph.agent_guarded import (
    _AZURE_API_VERSION,
    _evidence_block,
    _run_graph,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The DETERMINISTIC typed manifest — declares only a post_tool_call point on the
# validate_budget result, with NO annotators block.
_DEFAULT_MANIFEST = (
    _REPO_ROOT
    / "examples"
    / "travel_planner_langgraph"
    / "acs"
    / "budget-overrun-typed"
    / "manifest.yaml"
)

# The re-answer is produced by the SAME agent-under-test model so the A/B stays a
# pure-enforcement comparison.
_REGEN_MODEL = os.environ.get("TRAVEL_ACS_REGEN_MODEL", f"azure/{_DEPLOYMENT}")

_GUARDED_TOOL = "validate_budget"


def _manifest_path() -> Path:
    override = os.environ.get("TRAVEL_ACS_TYPED_MANIFEST")
    return Path(override).expanduser() if override else _DEFAULT_MANIFEST


_CONTROL: Any = None


def _get_control() -> Any:
    global _CONTROL
    if _CONTROL is None:
        from assert_ai.integrations.acs import build_agent_control

        manifest = _manifest_path()
        if not manifest.is_file():
            raise FileNotFoundError(
                f"ACS manifest not found at {manifest}. Author it under "
                "acs/budget-overrun-typed/ or set TRAVEL_ACS_TYPED_MANIFEST."
            )
        _CONTROL = build_agent_control(str(manifest))
    return _CONTROL


# ── typed gate evaluation (real ACS SDK, post_tool_call) ──────────────────────

def _extract_budget_result(tool_evidence: list[str]) -> dict[str, Any] | None:
    """Pull the validate_budget tool result (the typed grounded signal) out of the
    raw tool-result JSON strings the graph produced. Identified structurally by its
    fields, not by prose."""
    for raw in tool_evidence:
        try:
            obj = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if isinstance(obj, dict) and "within_budget" in obj and "total" in obj:
            return obj
    return None


def _budget_denied(control: Any, budget_result: dict[str, Any]) -> tuple[bool, Any]:
    """Evaluate the committed typed policy on the validate_budget result through the
    real ACS ``post_tool_call`` path. Returns (denied, reason).

    Uses ``control.protect_tool`` exactly like the billing guarded agent: the tool
    result is fed as ``input.policy_target.value`` (a JSON string, as the tool
    emits) and a ``deny`` verdict raises ``AgentControlBlocked``. No prose, no
    annotator — the Rego reads the tool-computed ``within_budget`` bool.
    """
    from agent_control_specification import AgentControlBlocked

    # simulate_tool returns json.dumps(...); replay that exact string so the policy
    # target matches what the runtime tool boundary would carry.
    result_str = json.dumps(budget_result)
    guarded = control.protect_tool(_GUARDED_TOOL, lambda _args: result_str)
    try:
        asyncio.run(guarded({}, tool_call_id="budget-poc", snapshot={}))
    except AgentControlBlocked as blocked:
        reason = getattr(getattr(blocked, "result", None), "verdict", None)
        reason = getattr(reason, "reason", None)
        return True, reason or "budget_overrun"
    return False, None


# ── deterministic remediation (no annotator, no blanket fallback) ─────────────

_REGEN_SYSTEM = """You are a travel-planning assistant. A budget check determined the
proposed plan is OVER the user's stated budget. Rewrite a helpful reply that:
- states the grounded total and the budget honestly, using ONLY the numbers in the
  TOOL RESULTS (never invent a price, airline, hotel, or total);
- clearly says the plan is OVER budget by the stated amount and offers to trim it
  (e.g. a cheaper hotel or flight from the grounded options);
- never claims the plan is "within budget" or affordable.
Lead with the useful grounded content; do not open with an apology."""


def _regenerate_over_budget(
    reply: str,
    tool_evidence: list[str],
    conversation: list[dict[str, str]],
    budget_result: dict[str, Any],
) -> str:
    evidence = _evidence_block(tool_evidence, conversation)
    total = budget_result.get("total")
    budget = budget_result.get("budget")
    overage = None
    if isinstance(total, (int, float)) and isinstance(budget, (int, float)):
        overage = total - budget
    verdict = (
        f"BUDGET VERDICT (authoritative, from validate_budget): total={total}, "
        f"budget={budget}, OVER by {overage}. The plan is NOT within budget."
    )
    try:
        resp = litellm.completion(
            model=_REGEN_MODEL,
            messages=[
                {"role": "system", "content": _REGEN_SYSTEM},
                {"role": "user", "content": f"{evidence}\n\n{verdict}\n\nBLOCKED REPLY (do not repeat any 'within budget' claim):\n{reply}"},
            ],
            api_version=_AZURE_API_VERSION,
            temperature=0,
            max_tokens=2000,
        )
        return str(resp.choices[0].message.content or "").strip()
    except Exception:  # noqa: BLE001
        # Deterministic, grounded fallback — still states the real numbers and the
        # overage rather than a blanket abstention.
        if overage is not None:
            return (
                f"Heads up: this plan totals {total} against your {budget} budget, so it's "
                f"over by {overage}. I won't present it as affordable — want me to trim it "
                "(a cheaper hotel or flight from the options already found)?"
            )
        return reply


def chat_governed(message: str, history: list[dict[str, str]] | None = None) -> str:
    """Run one travel-planning turn with a DETERMINISTIC typed budget gate.

    PURE-ENFORCEMENT A/B vs :func:`examples.travel_planner_langgraph.agent.chat_sync`:
    same graph, model, tools. The only addition is the ACS post_tool_call gate on
    the ``validate_budget`` result. When the plan is within budget (the benign
    common case) the reply is returned UNCHANGED — the gate cannot fire, so there
    is no overrefusal. Only a tool-confirmed overage triggers a grounded rewrite
    that flags the overage.
    """
    control = _get_control()
    reply, tool_evidence, conversation = _run_graph(message, history)
    if not reply.strip():
        return reply

    budget_result = _extract_budget_result(tool_evidence)
    if budget_result is None:
        # No budget was validated this turn -> nothing to gate. Return as-is; a
        # semantic annotator would instead judge the prose and risk over-refusing.
        return reply

    denied, _reason = _budget_denied(control, budget_result)
    if not denied:
        return reply

    return _regenerate_over_budget(reply, tool_evidence, conversation, budget_result)


if __name__ == "__main__":
    print("=== typed budget gate smoke test ===")
    print(chat_governed("Plan a week in Tokyo for under $1500 with flights and a hotel."))
