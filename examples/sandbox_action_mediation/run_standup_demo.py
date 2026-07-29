# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Interactive five-minute standup demo for the stock ASSERT sandbox path."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SETUP = HERE / "assert-setup-container.yaml"
RUNNER = HERE / "run_stock_scenario.py"


def slide(title: str, detail: str) -> None:
    print("\n" + "=" * 76, flush=True)
    print(title, flush=True)
    print("=" * 76, flush=True)
    print(detail, flush=True)


def wait_for_advance(enabled: bool, prompt: str = "Press SPACE or ENTER to continue...") -> None:
    if not enabled:
        return
    print(f"\n{prompt}", end="", flush=True)
    if not sys.stdin.isatty():
        input()
        return

    # The standup path runs in WSL over SSH from a Mac Terminal. Read one key in
    # cbreak mode so SPACE advances immediately without requiring ENTER.
    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        previous = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                key = sys.stdin.read(1)
                if key in {" ", "\r", "\n"}:
                    break
                if key in {"q", "Q", "\x03"}:
                    raise KeyboardInterrupt
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        print(flush=True)
    except (ImportError, OSError):
        input()


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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="run continuously for preflight/automation instead of waiting for keys",
    )
    args = parser.parse_args()
    interactive = not args.no_pause

    try:
        slide(
            "Sandboxed action mediation in ASSERT",
            "ASSERT evals deliberately try to make agents take risky actions. The stock "
            "sandbox lets safe operations run against disposable state, suppresses "
            "irreversible effects, blocks undeclared network access, and preserves every "
            "attempt as judge evidence.\n\n"
            "This demo uses a fixed input so the proof does not depend on model availability.",
        )
        wait_for_advance(interactive, "Press SPACE or ENTER to validate the setup...")

        slide(
            "1/3  Validate the user's sandbox setup",
            "The user supplies a configured agent image, policy.yaml, mocks.yaml, and "
            "optional cassettes. ASSERT checks that they agree before starting Docker.",
        )
        wait_for_advance(interactive, "Press SPACE or ENTER to run validation...")
        run(
            sys.executable,
            "-m",
            "assert_ai.integrations.sandbox.cli",
            "validate",
            str(SETUP),
        )
        wait_for_advance(interactive)

        slide(
            "2/3  Preview one irreversible action",
            "Policy decides whether send_message may execute. Only after policy selects "
            "mock does ASSERT resolve the argument-specific synthetic response. The mock "
            "file cannot weaken the policy decision.",
        )
        wait_for_advance(interactive, "Press SPACE or ENTER to resolve send_message...")
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
        wait_for_advance(interactive)

        slide(
            "3/3  Run the real stock Docker sandbox",
            "ASSERT starts a fresh hardened container, sends one fixed turn through normal "
            "inference, records tool and network evidence, and tears the sandbox down.\n\n"
            "Watch for three facts:\n"
            "  • lookup_customer passes and really executes\n"
            "  • send_message is mocked and its real implementation does not execute\n"
            "  • undeclared example.com egress is denied",
        )
        wait_for_advance(interactive, "Press SPACE or ENTER to start the sandbox...")
        run(sys.executable, str(RUNNER), "--check-baseline")
        wait_for_advance(interactive)

        slide(
            "Cleanup check",
            "A fresh sandbox is owned by one test case. No ASSERT container or network "
            "should remain after the inference turn.",
        )
        wait_for_advance(interactive, "Press SPACE or ENTER to verify cleanup...")
        containers = docker_resource_count("container", "assert-sandbox-")
        networks = docker_resource_count("network", "assert-sandbox-net-")
        print(f"Remaining ASSERT containers: {containers}")
        print(f"Remaining ASSERT networks:   {networks}")
        if containers or networks:
            raise RuntimeError("sandbox cleanup left Docker resources behind")
        wait_for_advance(interactive)

        slide(
            "What this means for C11",
            "The core ASSERT path now works end to end: setup, disposable container "
            "lifecycle, pass/mock/block enforcement, denied egress, and judge-visible "
            "evidence.\n\n"
            "The planning question is whether C11 should focus on onboarding real agents "
            "and hardening setup from their feedback, and whether to commit to one tailored "
            "Red Teaming consumer. A generic sandbox platform is not required for this proof.",
        )
        wait_for_advance(interactive, "Press SPACE or ENTER to finish...")
        print("\nDEMO COMPLETE: pass/mock/egress evidence was produced and cleanup succeeded.")
        return 0
    except KeyboardInterrupt:
        print("\n\nDemo stopped by presenter.", file=sys.stderr)
        return 130
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"\nDEMO FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
