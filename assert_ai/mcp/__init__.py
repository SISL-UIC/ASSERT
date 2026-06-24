# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""MCP server exposing ASSERT evaluation capabilities to AI agents and IDEs.

ASSERT is the MCP *server* (capability provider); an AI agent or IDE
(Claude Desktop, GitHub Copilot, Cursor, ...) is the *client*. The server is a
thin adapter over the existing programmatic surface — ``assert_ai.results``,
``assert_ai.library.loader`` and ``assert_ai.runner`` — which already return
JSON-able dictionaries.

Run it with the ``assert-ai-mcp`` console script (stdio transport).
"""

from assert_ai.mcp.server import build_server, main

__all__ = ["build_server", "main"]
