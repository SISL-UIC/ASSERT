# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Path-containment helpers for the MCP server.

Resource URIs (and some tool arguments) carry suite/run identifiers that become
filesystem path segments. A remote or careless client could otherwise send
``..`` or absolute paths to escape the configured results directory. These
helpers reject traversal up front — mirroring the sanitization the SvelteKit
viewer applies to manifest-provided artifact paths
(``viewer/src/lib/server/artifacts.ts``).
"""

from __future__ import annotations

from pathlib import Path

_UNSAFE_SEGMENTS = {"", ".", ".."}


def safe_subpath(base: Path, *segments: str) -> Path:
    """Join trusted ``base`` with untrusted ``segments``, rejecting traversal.

    Raises:
        ValueError: if any segment is empty, ``.``/``..``, contains a path
            separator, is absolute, or if the resolved path escapes ``base``.
    """
    base_resolved = base.resolve()
    for segment in segments:
        if (
            segment in _UNSAFE_SEGMENTS
            or "/" in segment
            or "\\" in segment
            or Path(segment).is_absolute()
        ):
            raise ValueError(f"Unsafe path segment: {segment!r}")

    candidate = base_resolved.joinpath(*segments).resolve()
    if candidate != base_resolved and not candidate.is_relative_to(base_resolved):
        raise ValueError("Resolved path escapes the results directory.")
    return candidate
