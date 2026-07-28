# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Small configured-agent endpoint used to exercise ASSERT's stock sandbox."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("PORT", "8080"))
POLICY = Path(os.environ.get("ACTION_MEDIATION_POLICY", "/sandbox/policy.json"))
MOCKS = Path(os.environ.get("ACTION_MEDIATION_MOCKS", "/sandbox/mocks.json"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return None

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("content-length", "0") or 0)
        json.loads(self.rfile.read(length) or b"{}")
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        mocks = json.loads(MOCKS.read_text(encoding="utf-8"))
        events = [{
            "role": "tool_result",
            "tool_name": "sandbox_configuration",
            "tool_args": {},
            "tool_call_id": "sandbox-config-1",
            "content": json.dumps({
                "policy_rules": len(policy.get("interactions") or []),
                "mock_rules": len(mocks.get("mocks") or []),
                "real_executed": False,
            }),
        }]
        # This reference agent deliberately attempts one harmless HTTP request
        # on every turn so the stock sandbox's deny-and-audit path is visible in
        # a normal ASSERT transcript.
        try:
            urllib.request.urlopen("http://example.com/attempt", timeout=10)  # noqa: S310
        except Exception:
            pass
        self._json(200, {
            "response": "The configured agent answered from inside the stock sandbox; its network probe was contained.",
            "events": events,
        })

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
