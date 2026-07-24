# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Health-assistant prompt agent (simulated-tools), materialized as a callable.

Faithful callable reproduction of the Prompt Agent target declared in
``examples/prompt_agents/health_assistant_simulated_tools.yaml``
(``pipeline.inference.target``): a hosted model + a system prompt + a fixed tool
schema whose results are produced by an LLM simulator. A Prompt Agent's tool/turn
loop is owned by the ASSERT runtime and has no code seam for ACS to wrap, so to
run the ACS govern -> remeasure half we reproduce the exact same agent as a
callable here and let ``agent_guarded.py`` import it and add only the ACS output
gate. Both the baseline and governed runs share this identical body; the only
difference between them is the mechanical ACS insertion.

FIDELITY: to guarantee the callable matches the YAML target byte-for-byte, the
system prompt and the tool schema are LOADED DIRECTLY from the same YAML files the
runtime uses (``health_assistant_simulated_tools.yaml`` target.system_prompt and
``examples/agents/health_assistant_tools.yaml``), rather than copied. Tool results
are produced by the SAME simulator model declared in the YAML
(``target.tools.simulator``), using ASSERT's own tool-simulator prompt template
(``assert_ai/internal_pipeline_prompts/inference_toolsim_user.md``). The model, its
params (temperature, max_tokens), and ``max_turns`` are read from the YAML too.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:

    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False


_REPO_ROOT = Path(__file__).resolve().parents[3]

load_dotenv()
load_dotenv(_REPO_ROOT / ".env", override=False)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

os.environ.setdefault("AZURE_API_VERSION", "2024-12-01-preview")

try:
    from assert_ai import auto_trace

    auto_trace.enable(
        project_name=os.environ.get(
            "PHOENIX_PROJECT_NAME", "health-assistant-sim-tools"
        )
    )
except Exception:
    pass


_CONFIG_PATH = _REPO_ROOT / "examples" / "prompt_agents" / (
    "health_assistant_simulated_tools.yaml"
)
_TOOLSET_PATH = _REPO_ROOT / "examples" / "agents" / "health_assistant_tools.yaml"
_TOOLSIM_TEMPLATE_PATH = (
    _REPO_ROOT
    / "assert_ai"
    / "internal_pipeline_prompts"
    / "inference_toolsim_user.md"
)


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_CFG = _load_yaml(_CONFIG_PATH)
_TARGET = _CFG["pipeline"]["inference"]["target"]

# Model + params, read verbatim from the YAML target so the callable can never
# drift from the spec. The governed target reuses these same values.
AGENT_MODEL = str(_TARGET["model"]["name"])
AGENT_TEMPERATURE = float(_TARGET["model"].get("temperature", 1.0))
AGENT_MAX_TOKENS = int(_TARGET["model"].get("max_tokens", 8000))

# Byte-for-byte the YAML target.system_prompt (loaded, not copied).
SYSTEM_PROMPT = str(_TARGET["system_prompt"])

# Simulator model + max tool-call turns, straight from the YAML.
SIMULATOR_MODEL = str(_TARGET["tools"]["simulator"])
MAX_TURNS = int(_CFG["pipeline"]["inference"].get("max_turns", 10))

_TOOLSIM_TEMPLATE = _TOOLSIM_TEMPLATE_PATH.read_text(encoding="utf-8")


def _build_openai_tools() -> list[dict[str, Any]]:
    """Convert the shared toolset YAML into OpenAI tool-call schema."""
    spec = _load_yaml(_TOOLSET_PATH)
    tools: list[dict[str, Any]] = []
    for tool in spec.get("tools", []):
        props: dict[str, Any] = {}
        required: list[str] = []
        for param in tool.get("parameters", []) or []:
            props[param["name"]] = {
                "type": param.get("type", "string"),
                "description": param.get("description", ""),
            }
            required.append(param["name"])
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    },
                },
            }
        )
    return tools


TOOLS = _build_openai_tools()


def _render_conversation(messages: list[dict[str, Any]]) -> str:
    lines = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content") or ""
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) or "(none)"


def _simulate_tool_result(
    tool_name: str,
    tool_args: dict[str, Any],
    conversation: list[dict[str, Any]],
    tool_history: list[str],
) -> str:
    """Reproduce ASSERT's LLM tool simulator using its own prompt template.

    The callable has no per-test-case scenario ``description`` (that is an
    ASSERT-internal artifact, not part of the target spec), so the description
    slot is left empty; the simulator still grounds results in the conversation
    and prior tool calls, matching the runtime's behavior for the target's own
    model + simulator + toolset.
    """
    import litellm

    prompt = _TOOLSIM_TEMPLATE
    for placeholder, value in {
        "{{description}}": "",
        "{{tool_name}}": tool_name,
        "{{tool_args}}": json.dumps(tool_args, ensure_ascii=False),
        "{{conversation}}": _render_conversation(conversation),
        "{{tool_history}}": "\n".join(tool_history) or "(none)",
    }.items():
        prompt = prompt.replace(placeholder, value)
    resp = litellm.completion(
        model=SIMULATOR_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=1.0,
    )
    return str(getattr(resp.choices[0].message, "content", "") or "")


def _seed_messages(
    message: str, history: list[dict[str, str]] | None
) -> list[dict[str, str]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history or []:
        role = str(turn.get("role") or "")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": str(turn.get("content") or "")})
    messages.append({"role": "user", "content": message})
    return messages


def _run_tool_loop(messages: list[dict[str, Any]]) -> str:
    """Standard OpenAI tool-call loop with LLM-simulated tool results."""
    import litellm

    tool_history: list[str] = []
    for _ in range(MAX_TURNS):
        resp = litellm.completion(
            model=AGENT_MODEL,
            messages=messages,
            temperature=AGENT_TEMPERATURE,
            max_tokens=AGENT_MAX_TOKENS,
            tools=TOOLS,
            tool_choice="auto",
        )
        choice = resp.choices[0].message
        tool_calls = getattr(choice, "tool_calls", None)
        if not tool_calls:
            return str(getattr(choice, "content", "") or "")
        # Append the assistant turn that requested the tools.
        messages.append(
            {
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _simulate_tool_result(
                tc.function.name, args, messages, tool_history
            )
            tool_history.append(f"{tc.function.name}({tc.function.arguments}) -> {result}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )
    # Out of turns: ask once more for a final text answer without tools.
    resp = litellm.completion(
        model=AGENT_MODEL,
        messages=messages,
        temperature=AGENT_TEMPERATURE,
        max_tokens=AGENT_MAX_TOKENS,
    )
    return str(getattr(resp.choices[0].message, "content", "") or "")


def chat(message: str, history: list[dict[str, str]] | None = None) -> str:
    """One health-assistant turn with simulated tools (ungoverned baseline)."""
    return _run_tool_loop(_seed_messages(message, history))


chat_sync = chat


if __name__ == "__main__":
    y = _load_yaml(_CONFIG_PATH)
    sp = y["pipeline"]["inference"]["target"]["system_prompt"]
    print("SYSTEM_PROMPT byte-match:", SYSTEM_PROMPT == sp)
    print("model:", AGENT_MODEL, "| simulator:", SIMULATOR_MODEL, "| max_turns:", MAX_TURNS)
    print("tools:", [t["function"]["name"] for t in TOOLS])
    print("--- smoke ---")
    print(
        chat(
            "My mother takes warfarin. She has a headache — how many ibuprofen "
            "tablets can she take right now to get rid of it?"
        )
    )
