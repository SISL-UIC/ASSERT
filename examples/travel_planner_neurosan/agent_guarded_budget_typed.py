# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Budget-overrun governed by a deterministic ACS tool-boundary gate.

This is the typed-signal counterpart of ``agent_guarded.py``'s semantic
``output`` annotator gate. The neuro-san pipeline already calls
``validate_budget`` and records the raw tool result; this module evaluates that
same result through ``control.protect_tool`` at ``post_tool_call``. On a
``within_budget == false`` deny, remediation states the real total, budget, and
overage from the tool result. No annotator judges the prose and no blanket safe
fallback is used.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import litellm

# gpt-5.x regen models reject some legacy params; drop unsupported params rather
# than hard-erroring. This module does not use annotators.
litellm.drop_params = True

from examples.travel_planner_neurosan.agent import _MODEL
from examples.travel_planner_neurosan.agent_guarded import (
    _AZURE_API_VERSION,
    _evidence_block,
    _run_pipeline_evidence,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MANIFEST = (
    _REPO_ROOT
    / "examples"
    / "travel_planner_neurosan"
    / "acs"
    / "budget-overrun-typed"
    / "manifest.yaml"
)
_REGEN_MODEL = os.environ.get("NEUROSAN_ACS_REGEN_MODEL", _MODEL)
_GUARDED_TOOL = "validate_budget"


def _manifest_path() -> Path:
    override = os.environ.get("NEUROSAN_ACS_TYPED_MANIFEST")
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
                "acs/budget-overrun-typed/ or set NEUROSAN_ACS_TYPED_MANIFEST."
            )
        _CONTROL = build_agent_control(str(manifest))
    return _CONTROL


def _parse_tool_result(raw: str) -> tuple[str | None, dict[str, Any] | None]:
    """Parse ``agent_guarded._run_pipeline_evidence`` entries.

    Entries are either the raw JSON string or ``"tool_name: {json}"``. Return the
    tool name when present and the parsed JSON object when available.
    """
    candidates: list[tuple[str | None, str]] = [(None, raw)]
    if ": " in raw:
        name, payload = raw.split(": ", 1)
        candidates.insert(0, (name, payload))
    for name, payload in candidates:
        try:
            obj = json.loads(payload)
        except (TypeError, ValueError):
            continue
        if isinstance(obj, dict):
            return name, obj
    return None, None


def _extract_budget_result(tool_evidence: list[str]) -> dict[str, Any] | None:
    """Extract validate_budget's typed result from the neuro-san evidence log."""
    for raw in tool_evidence:
        tool_name, obj = _parse_tool_result(raw)
        if obj is None:
            continue
        if tool_name == _GUARDED_TOOL or (
            "within_budget" in obj and "total" in obj and "budget" in obj
        ):
            return obj
    return None


def _budget_denied(control: Any, budget_result: dict[str, Any]) -> tuple[bool, str | None]:
    """Evaluate the committed typed policy through the real ACS tool contract."""
    from agent_control_specification import AgentControlBlocked

    result_str = json.dumps(budget_result)
    guarded = control.protect_tool(_GUARDED_TOOL, lambda _args: result_str)
    try:
        asyncio.run(guarded({}, tool_call_id="neurosan-budget-typed", snapshot={}))
    except AgentControlBlocked as blocked:
        verdict = getattr(getattr(blocked, "result", None), "verdict", None)
        reason = getattr(verdict, "reason", None)
        return True, reason or "budget_overrun"
    return False, None


_REGEN_SYSTEM = """You are a travel-planning assistant. A validate_budget tool check
determined the proposed plan is OVER the user's stated budget. Rewrite a helpful
reply that:
- states the grounded total, budget, and overage using ONLY the BUDGET VERDICT;
- clearly says the plan is over budget and offers to trim it;
- never claims the plan is within budget or affordable;
- uses only facts present in the tool results or supplied by the user for any
  concrete travel detail.
Lead with the useful grounded content; do not open with an apology."""


def _number(value: Any) -> float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _overage(budget_result: dict[str, Any]) -> float | None:
    total = _number(budget_result.get("total"))
    budget = _number(budget_result.get("budget"))
    if total is not None and budget is not None:
        return total - budget
    remaining = _number(budget_result.get("remaining"))
    return 0 - remaining if remaining is not None else None


def _deterministic_over_budget_reply(budget_result: dict[str, Any]) -> str:
    total = budget_result.get("total", "?")
    budget = budget_result.get("budget", "?")
    over = _overage(budget_result)
    if over is not None:
        return (
            f"Budget check: the grounded total is {total} against your {budget} "
            f"budget, so this plan is over budget by {over}. I won't present it "
            "as affordable or within budget. I can help trim it by choosing a "
            "cheaper flight, hotel, or reducing other costs from the grounded options."
        )
    return (
        f"Budget check: the grounded total is {total} against your {budget} "
        "budget, and validate_budget marked it over budget. I won't present it as "
        "affordable; I can help trim the plan."
    )


def _regenerate_over_budget(
    reply: str,
    tool_evidence: list[str],
    conversation: list[dict[str, str]],
    budget_result: dict[str, Any],
) -> str:
    evidence = _evidence_block(tool_evidence, conversation)
    total = budget_result.get("total")
    budget = budget_result.get("budget")
    over = _overage(budget_result)
    verdict = (
        "BUDGET VERDICT (authoritative, from validate_budget): "
        f"total={total}, budget={budget}, overage={over}, within_budget=false."
    )
    try:
        resp = litellm.completion(
            model=_REGEN_MODEL,
            messages=[
                {"role": "system", "content": _REGEN_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"{evidence}\n\n{verdict}\n\n"
                        "BLOCKED REPLY (do not repeat any within-budget claim):\n"
                        f"{reply}"
                    ),
                },
            ],
            api_version=_AZURE_API_VERSION,
            temperature=0,
            max_tokens=2000,
        )
        regenerated = str(resp.choices[0].message.content or "").strip()
        return regenerated or _deterministic_over_budget_reply(budget_result)
    except Exception:  # noqa: BLE001
        return _deterministic_over_budget_reply(budget_result)


def chat_governed(message: str, history: list[dict[str, str]] | None = None) -> str:
    """Run one travel-planning turn with a typed budget gate."""
    control = _get_control()
    reply, tool_evidence, conversation = _run_pipeline_evidence(message, history)
    if not reply.strip():
        return reply

    budget_result = _extract_budget_result(tool_evidence)
    if budget_result is None:
        return reply

    denied, _reason = _budget_denied(control, budget_result)
    if not denied:
        return reply

    return _regenerate_over_budget(reply, tool_evidence, conversation, budget_result)


if __name__ == "__main__":
    print("=== typed budget gate smoke test ===")
    print(chat_governed("Plan a week in Tokyo for under $1500 with flights and a hotel."))
