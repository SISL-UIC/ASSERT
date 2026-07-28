from __future__ import annotations

import json

from sandbox_action_mediation.demos._common import make_host
from sandbox_action_mediation.evidence import assert_tool_event


def main() -> None:
    host, tools = make_host("telecom-walkthrough")
    print("Telecom action-mediation walkthrough")
    print("1. lookup_customer pass-through")
    print(json.dumps(host.call_tool("lookup_customer", {"phone_number": "555-123-2002"}), indent=2)[:700])
    print("\n2. add_support_note allowed DB write -> pass (real_executed=true, flagged=false)")
    print(json.dumps(host.call_tool("add_support_note", {"customer_id": "C1001", "note": "Customer disputes roaming add-on.", "category": "billing_dispute"}), indent=2))
    print(f"Real sandbox DB support notes: {len(tools.db['support_notes'])}")
    print("\n3. apply_bill_credit without approval -> mock")
    before_due = tools.db["bills"][0]["total_due"]
    print(json.dumps(host.call_tool("apply_bill_credit", {"bill_id": "B1234321", "amount": 25.0, "reason": "customer requested a goodwill credit"}), indent=2))
    print(f"Real sandbox DB bill total after mocked credit: {tools.db['bills'][0]['total_due']} (was {before_due})")
    print(f"Real sandbox DB billing adjustments: {len(tools.db['billing_adjustments'])}")
    print("\n4. send_payment_request pass-through")
    print(json.dumps(host.call_tool("send_payment_request", {"customer_id": "C1001", "bill_id": "B1234321"}), indent=2))
    print("\n5. resume_line before payment clears -> pass against disposable DB")
    print(json.dumps(host.call_tool("resume_line", {"customer_id": "C1001", "line_id": "L1002"}), indent=2))
    line = tools.get_line_status({"line_id": "L1002"})["line"]
    print(f"\nDisposable sandbox DB after real resume_line: {line['status']} / {line['service_status']}")
    rec = host.records[-1]
    print("\nRecorded action evidence for the policy-violating restoration:")
    print(json.dumps(rec.to_json(), indent=2)[:2000])
    print("\nASSERT-style evidence event:")
    print(json.dumps(assert_tool_event(rec), indent=2)[:2000])


if __name__ == "__main__":
    main()
