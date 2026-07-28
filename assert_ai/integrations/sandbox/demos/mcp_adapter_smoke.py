from __future__ import annotations

import json

from sandbox_action_mediation.demos._common import make_host
from sandbox_action_mediation.mcp_adapter import MCPToolHostAdapter


def main() -> None:
    host, tools = make_host("mcp-adapter-smoke")
    adapter = MCPToolHostAdapter(host)
    result = adapter.call_tool({"name": "resume_line", "arguments": {"customer_id": "C1001", "line_id": "L1002"}})
    line = tools.get_line_status({"line_id": "L1002"})["line"]
    record = host.records[-1]
    print("MCP adapter smoke")
    print("result:", json.dumps(result, sort_keys=True))
    print("real line status:", line["status"], line["service_status"])
    print("agent hooks point:", record.pre_context["interception_point"], "->", record.post_context["interception_point"])
    print("mode:", record.decision.mode, "real_executed:", record.decision.real_executed, "flagged:", record.decision.flagged)
    if line["status"] != "active" or not record.decision.real_executed:
        raise SystemExit("resume_line did not update the disposable backend coherently")
    print("OK: MCP-style call went through Agent Hooks-shaped action mediation")


if __name__ == "__main__":
    main()
