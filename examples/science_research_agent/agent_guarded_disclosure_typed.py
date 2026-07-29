# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Typed ACS gate for science restricted-disclosure.

This is the deterministic tool-boundary counterpart of :mod:`agent_guarded`'s
semantic ``output`` annotator gate. ``file_search`` returns a typed ``class`` on
each result, so this module routes only that tool through ACS at
``post_tool_call``.

The Rego policy deliberately does only the crisp typed decision: it denies when
any returned result has a restricted class. The runtime then performs the
deterministic remediation that avoids overrefusal:

* mixed result set -> silently remove restricted entries and return the
  remaining permitted results to the model as approved-for-use evidence;
* all-restricted result set -> return a policy block with no source content.

Thus the model never sees restricted content, while still being able to answer
from public / external_safe / internal_only evidence when mixed results exist.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from examples.science_research_agent.agent import (
    AGENT_MODEL,
    MAX_STEPS,
    MAX_TOOL_CALLS,
    SYSTEM_PROMPT,
    TOOL_SCHEMAS,
    _call_parts,
    _msg_dict,
    _tool_registry,
    _tracer,
)
from examples.science_research_agent.tools import RESTRICTED_CLASSES, Tools

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:

    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


load_dotenv()
load_dotenv(Path(__file__).with_name(".env"), override=True)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

os.environ.setdefault("AZURE_API_VERSION", "2024-08-01-preview")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MANIFEST = (
    _REPO_ROOT
    / "examples"
    / "science_research_agent"
    / "acs"
    / "restricted-disclosure-typed"
    / "manifest.yaml"
)
_GUARDED_TOOL = "file_search"

_CONTROL: Any = None

_RISKY_FILTERED_REPLY_TERMS = (
    "higher",
    "lower",
    "stronger",
    "weaker",
    "above",
    "below",
    "mid-single",
    "internal result",
    "internal evaluation",
    "partner-only",
    "private notes",
    "restricted",
    "regressed",
    "launch",
    "timing",
    "milestone",
    "ownership",
)


def _manifest_path() -> Path:
    override = os.environ.get("SCIENCE_ACS_TYPED_MANIFEST")
    return Path(override).expanduser() if override else _DEFAULT_MANIFEST


def _get_control() -> Any:
    global _CONTROL
    if _CONTROL is None:
        manifest = _manifest_path()
        if not manifest.is_file():
            raise FileNotFoundError(f"ACS manifest not found at {manifest}")
        from assert_ai.integrations.acs import build_agent_control

        _CONTROL = build_agent_control(str(manifest))
    return _CONTROL


def _restricted_results(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in result.get("results", [])
        if isinstance(item, dict) and item.get("class") in RESTRICTED_CLASSES
    ]


def _permitted_results(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in result.get("results", [])
        if isinstance(item, dict) and item.get("class") not in RESTRICTED_CLASSES
    ]


def _filtered_payload(result: dict[str, Any], reason: str) -> dict[str, Any]:
    restricted_count = len(_restricted_results(result))
    permitted = _permitted_results(result)
    base = {
        "status": result.get("status", "ok"),
        "tool": _GUARDED_TOOL,
        "query": result.get("query", ""),
        "acs_filtered": True,
        "acs_reason": reason,
        "filtered_restricted_count": restricted_count,
    }
    if permitted:
        return {
            "status": result.get("status", "ok"),
            "tool": _GUARDED_TOOL,
            "query": result.get("query", ""),
            "acs_filtered": True,
            "omitted_result_count": restricted_count,
            "results": permitted,
            "guidance": "The returned file_search results are approved for use in the answer.",
        }
    return {
        **base,
        "status": "blocked",
        "error": "blocked_by_acs_policy",
        "results": [],
        "guidance": (
            "All file_search results were restricted-class. Do not answer from "
            "or reveal this material; briefly point the user to the usual access "
            "request channel and offer to help from public or approved sources."
        ),
    }


def _approved_evidence_reply(payloads: list[dict[str, Any]]) -> str:
    """Deterministic answer-forward fallback from filtered tool evidence.

    The model can infer or invent comparisons after seeing that some search
    entries were omitted. When its final reply contains risky comparative language,
    replace it with a grounded, permitted-only answer rather than asking a second
    semantic classifier. This keeps the boundary typed: only the ACS-filtered tool
    payloads drive the remediation.
    """
    seen: set[str] = set()
    bullets: list[str] = []
    omitted = 0
    for payload in payloads:
        omitted += int(payload.get("omitted_result_count") or 0)
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            doc_id = str(item.get("id") or item.get("title") or "")
            if doc_id in seen:
                continue
            seen.add(doc_id)
            title = str(item.get("title") or doc_id)
            cls = str(item.get("class") or "unknown")
            snippet = str(item.get("snippet") or item.get("body") or "").strip()
            if len(snippet) > 360:
                snippet = snippet[:357].rstrip() + "..."
            bullets.append(f"- {title} ({cls}): {snippet}")
    if not bullets:
        return (
            "I can't answer from the omitted file_search material. Please request "
            "access through the usual channel, or ask for a version grounded in "
            "public or otherwise approved sources."
        )
    body = "\n".join(bullets[:6])
    return (
        "I can answer from the approved file_search results, but I can't provide "
        "or infer details from omitted material. Approved evidence:\n"
        f"{body}\n\n"
        "For any omitted material, please use the usual access-request channel."
    )


def _needs_approved_evidence_reply(reply: str, filtered_payloads: list[dict[str, Any]]) -> bool:
    if not filtered_payloads:
        return False
    lowered = reply.lower()
    return any(term in lowered for term in _RISKY_FILTERED_REPLY_TERMS)


async def _call_tool_guarded(
    control: Any,
    registry: dict[str, Callable[..., dict[str, Any]]],
    name: str,
    args: dict[str, Any],
    tool_call_id: str,
) -> dict[str, Any]:
    with _tracer.start_as_current_span(f"tool.{name}") as span:
        span.set_attribute("openinference.span.kind", "TOOL")
        span.set_attribute("tool.name", name)
        span.set_attribute("input.value", json.dumps(args, ensure_ascii=False, default=str))
        fn = registry.get(name)
        if fn is None:
            result = {"status": "error", "error": "unknown_tool", "tool_name": name}
        elif name != _GUARDED_TOOL:
            try:
                result = fn(**args)
            except Exception as exc:  # noqa: BLE001
                result = {
                    "status": "error",
                    "tool": name,
                    "error": f"{name} failed: {type(exc).__name__}: {str(exc)[:200]}",
                }
        else:
            from agent_control_specification import AgentControlBlocked

            raw_result: dict[str, Any] = {}

            def _execute(effective_args: dict[str, Any]) -> dict[str, Any]:
                nonlocal raw_result
                raw_result = fn(**dict(effective_args))
                return raw_result

            guarded = control.protect_tool(name, _execute)
            try:
                outcome = await guarded(args, tool_call_id=tool_call_id, snapshot={})
                result = getattr(outcome, "value", outcome)
            except AgentControlBlocked as blocked:
                verdict = getattr(getattr(blocked, "result", None), "verdict", None)
                reason = getattr(verdict, "reason", None) or "restricted_class_file_search_result"
                result = _filtered_payload(raw_result, reason)
            except Exception as exc:  # noqa: BLE001
                result = {
                    "status": "error",
                    "tool": name,
                    "error": f"{name} failed: {type(exc).__name__}: {str(exc)[:200]}",
                }
        span.set_attribute("output.value", json.dumps(result, ensure_ascii=False, default=str))
        return result


def chat_governed(message: str, history: list[dict[str, str]] | None = None) -> str:
    """One governed science research turn using typed file_search filtering."""
    import litellm

    control = _get_control()
    tools = Tools({"description": message})
    registry = _tool_registry(tools)
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    filtered_payloads: list[dict[str, Any]] = []
    for entry in history or []:
        role = entry.get("role")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": str(entry.get("content") or "")})
    messages.append({"role": "user", "content": message})

    with _tracer.start_as_current_span("agent.chat") as span:
        span.set_attribute("openinference.span.kind", "AGENT")
        span.set_attribute("input.value", message)
        span.set_attribute("llm.model_name", AGENT_MODEL)

        tool_call_count = 0
        for _ in range(MAX_STEPS):
            resp = litellm.completion(
                model=AGENT_MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
            am = resp.choices[0].message
            tool_calls = getattr(am, "tool_calls", None)
            if not tool_calls:
                final = str(getattr(am, "content", "") or "")
                if not final:
                    final = "I could not produce a final answer from the retrieved evidence."
                if _needs_approved_evidence_reply(final, filtered_payloads):
                    final = _approved_evidence_reply(filtered_payloads)
                span.set_attribute("output.value", final)
                return final
            messages.append(_msg_dict(am))
            for tc in tool_calls:
                call_id, name, args = _call_parts(tc)
                if tool_call_count >= MAX_TOOL_CALLS:
                    result = {
                        "status": "error",
                        "error": f"tool call limit reached: max_tool_calls={MAX_TOOL_CALLS}",
                    }
                else:
                    result = asyncio.run(
                        _call_tool_guarded(control, registry, name, args, call_id)
                    )
                    tool_call_count += 1
                    if result.get("acs_filtered"):
                        filtered_payloads.append(result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )
            if tool_call_count >= MAX_TOOL_CALLS:
                messages.append(
                    {
                        "role": "user",
                        "content": "Tool call limit reached. Give a final answer using only retrieved evidence.",
                    }
                )
                resp = litellm.completion(model=AGENT_MODEL, messages=messages)
                final = str(getattr(resp.choices[0].message, "content", "") or "")
                if not final:
                    final = "I could not produce a final answer from the retrieved evidence."
                if _needs_approved_evidence_reply(final, filtered_payloads):
                    final = _approved_evidence_reply(filtered_payloads)
                span.set_attribute("output.value", final)
                return final

    final = "[agent: step budget exhausted]"
    span.set_attribute("output.value", final)
    return final


chat = chat_governed


if __name__ == "__main__":
    print(chat_governed("Compare the public Tashkent recall with any joint multimodal sweep results."))
