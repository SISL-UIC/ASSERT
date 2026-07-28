from __future__ import annotations

from pathlib import Path

from sandbox_action_mediation.mediator import ActionMediator
from sandbox_action_mediation.policy import MediationPolicy
from sandbox_action_mediation.telecom.tools import TelecomTools
from sandbox_action_mediation.tool_host import AgentHooksToolHost

ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "examples" / "telecom" / "policy.yaml"
CASSETTES = ROOT / "examples" / "telecom" / "cassettes"


def make_host(session_id: str = "demo-session"):
    tools = TelecomTools()
    policy = MediationPolicy.from_yaml(POLICY)
    mediator = ActionMediator(policy, cassette_dir=CASSETTES)
    host = AgentHooksToolHost(
        tools=tools.tool_map(),
        mediator=mediator,
        agent_id="telecom-support-agent",
        session_id=session_id,
    )
    return host, tools
