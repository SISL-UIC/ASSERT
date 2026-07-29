# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Narrated five-minute standup demo for the stock ASSERT sandbox path."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SETUP = HERE / "assert-setup-container.yaml"
RUNNER = HERE / "run_stock_scenario.py"


def announce(title: str, detail: str) -> None:
    print("\n" + "=" * 76, flush=True)
    print(title, flush=True)
    print("=" * 76, flush=True)
    print(detail, flush=True)


def run(*args: str) -> None:
    subprocess.run(list(args), check=True, cwd=HERE.parents[1])


def docker_resource_count(kind: str, name_filter: str) -> int:
    command = ["docker", kind, "ls"]
    if kind == "container":
        command.append("-a")
    command.extend(["-q", "--filter", f"name={name_filter}"])
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return len([line for line in result.stdout.splitlines() if line.strip()])


def main() -> int:
    try:
        announce(
            "1/3  Validate the user's sandbox setup",
            "ASSERT checks the configured agent target, policy, mocks, and cassettes "
            "before starting Docker.",
        )
        run(
            sys.executable,
            "-m",
            "assert_ai.integrations.sandbox.cli",
            "validate",
            str(SETUP),
        )

        announce(
            "2/3  Preview one irreversible action",
            "Policy decides whether send_message may execute. Only after policy selects "
            "mock does ASSERT resolve the argument-specific synthetic response.",
        )
        run(
            sys.executable,
            "-m",
            "assert_ai.integrations.sandbox.cli",
            "resolve",
            str(SETUP),
            "send_message",
            "--args",
            json.dumps({"recipient": "555-000-9999", "channel": "sms"}),
        )

        announce(
            "3/3  Run the real stock Docker sandbox",
            "ASSERT now starts a fresh hardened container, sends one fixed turn through "
            "normal inference, records tool and network evidence, and tears the sandbox down.\n"
            "Expected proof: the safe lookup really executes, the outbound message is "
            "mocked without executing its real implementation, and undeclared egress is denied.",
        )
        run(sys.executable, str(RUNNER), "--check-baseline")

        announce(
            "Cleanup check",
            "A fresh sandbox is owned by one test case. No ASSERT container or network "
            "should remain after the inference turn.",
        )
        containers = docker_resource_count("container", "assert-sandbox-")
        networks = docker_resource_count("network", "assert-sandbox-net-")
        print(f"Remaining ASSERT containers: {containers}")
        print(f"Remaining ASSERT networks:   {networks}")
        if containers or networks:
            raise RuntimeError("sandbox cleanup left Docker resources behind")

        print("\nDEMO COMPLETE: pass/mock/egress evidence was produced and cleanup succeeded.")
        return 0
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"\nDEMO FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
