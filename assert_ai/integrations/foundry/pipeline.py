# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""End-to-end orchestrator for the ``assert-ai foundry push`` command.

Composes the loader, evaluator spec builder, and row builder against
the ``azure-ai-projects`` SDK to publish an ASSERT run to a Foundry
project. The orchestrator can be called from Python as well — an
integration test or a downstream tool that already holds a loaded run
can skip the CLI entirely.

Push sequence (all via the ``azure-ai-projects`` SDK):

1. **Load the run** (:func:`load_run`).
2. **Build evaluator specs** — one Foundry custom evaluator per
   ASSERT judge dimension, per requested variant
   (:func:`build_evaluator_specs_for_run` with
   ``mode='code' | 'prompt' | 'both'``).
3. **Register evaluators idempotently** — for each spec, GET the
   named ``assert-{dim}[/-rescore]`` at version ``"1"`` first; POST
   only when it doesn't exist. Re-pushes reuse the existing catalog
   entry rather than churning versions.
4. **Build flat JSONL rows** (:func:`build_dataset_rows`) and their
   content hash (:func:`content_hash`). The hash becomes the dataset
   version so identical row content ⇒ identical version ⇒ dataset
   asset gets reused across pushes.
5. **Upload the dataset asset** — GET
   ``assert-{suite}/{content_hash}`` first; on 404 write bytes to a
   temp file and call ``datasets.upload_file(name, version, file_path)``.
   The SDK handles startPendingUpload + SAS PUT + register internally.
6. **Resolve the eval by name** — page the project's evals listing
   for one named ``ASSERT: {suite}``. If found, verify its
   ``testing_criteria`` still matches what we're about to send; on
   drift, fail loudly and instruct the user to bump ``--eval-name``.
   Foundry's ``POST /evals/{id}`` (Update eval) only accepts
   ``name`` + ``metadata`` — testing_criteria cannot be patched.
7. **Create the eval** if new, or reuse the existing id.
8. **Create the eval run** — always a fresh run per push so the UI
   renders run-over-run trends. Points at the dataset asset id from
   step 5 and threads through the workspace deployment name for the
   prompt-variant evaluators.

Dry-run mode short-circuits after step 4 with a
:class:`DryRunResult` carrying the resolved evaluator specs, dataset
row count, content hash, and the eval + run payloads it would have
POSTed.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from assert_ai.integrations.foundry.artifacts import AssertRun, load_run
from assert_ai.integrations.foundry.dataset import (
    build_dataset_rows,
    content_hash,
    rows_to_jsonl_bytes,
)
from assert_ai.integrations.foundry.evaluators import (
    AssertEvaluatorSpec,
    EvaluatorMode,
    build_evaluator_specs_for_run,
)


# ── Public constants ────────────────────────────────────────────────

EVAL_NAME_PREFIX = "ASSERT: "
"""Prefix on every eval definition the exporter creates. Lets a
customer filter ASSERT-owned evals in the Foundry UI and lets a
future ``foundry gc`` follow-up find them by name."""

RUN_NAME_PREFIX = "ASSERT run: "
"""Prefix on every eval run the exporter creates."""

DATASET_NAME_PREFIX = "assert-"
"""Prefix on every dataset asset the exporter registers. Sanitized
to Foundry's a-z / 0-9 / hyphen / underscore character class."""

_DATASET_EVALUATOR_TYPE = "azure_ai_evaluator"


class PushError(Exception):
    """Raised when a push cannot complete for a caller-visible reason."""


# ── Public data types ───────────────────────────────────────────────


@dataclass(frozen=True)
class EvaluatorRef:
    """A registered (or reused) Foundry evaluator, referenced by name+version."""

    dimension_id: str
    variant: str  # "code" | "prompt"
    evaluator_name: str
    evaluator_version: str


@dataclass(frozen=True)
class DatasetRef:
    """A registered (or reused) Foundry dataset asset."""

    name: str
    version: str
    asset_id: str


@dataclass(frozen=True)
class PushResult:
    """Everything the caller needs to know after a successful push."""

    eval_id: str
    run_id: str
    evaluator_refs: tuple[EvaluatorRef, ...]
    dataset_ref: DatasetRef
    reused_evaluators: tuple[str, ...]
    reused_dataset: bool
    reused_eval: bool


@dataclass(frozen=True)
class DryRunResult:
    """Preview of what the push would have done, with no network calls."""

    eval_name: str
    run_name: str
    dataset_name: str
    dataset_version: str
    dataset_row_count: int
    evaluator_specs: tuple[AssertEvaluatorSpec, ...]
    judge_deployment: str
    passing_when_true: Mapping[str, bool]


# ── Naming helpers ──────────────────────────────────────────────────


def default_eval_name(run: AssertRun) -> str:
    """``ASSERT: {suite_id}`` — one eval per suite, many runs under it."""
    return f"{EVAL_NAME_PREFIX}{run.suite_id}"


def default_run_name(run: AssertRun) -> str:
    """``ASSERT run: {run_id}`` — human-readable slot for this push."""
    return f"{RUN_NAME_PREFIX}{run.run_id}"


def default_dataset_name(run: AssertRun) -> str:
    """``assert-{suite_id}``, sanitized to Foundry's character class.

    Content-addressed at the *version* level (see :func:`content_hash`)
    so the dataset name stays stable across pushes and the Foundry UI
    groups all pushes of the same suite under one dataset entry.
    """
    import re

    raw = f"{DATASET_NAME_PREFIX}{run.suite_id}"
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", raw.lower()).strip("-")
    return cleaned or "assert-run"


def strip_litellm_prefix(model_name: str) -> str:
    """Return the deployment name with any LiteLLM ``provider/`` prefix removed.

    ASSERT configs commonly write ``azure/gpt-5.4-mini`` (LiteLLM
    identifier); Foundry's evaluator ``initialization_parameters.model``
    takes the bare deployment name.
    """
    if not isinstance(model_name, str) or "/" not in model_name:
        return model_name or ""
    return model_name.rsplit("/", 1)[1]


def resolve_judge_deployment(run: AssertRun) -> str:
    """Best-effort resolution of the judge model deployment name.

    Order: ``pipeline.judge.model.name`` → ``default_model.name`` →
    first non-empty ``judge_model`` from ``scores.jsonl`` → ``""``.
    LiteLLM ``provider/`` prefix is stripped.
    """
    for path in (("pipeline", "judge", "model"), ("default_model",)):
        node: Any = run.config
        for key in path:
            if not isinstance(node, Mapping):
                node = None
                break
            node = node.get(key)
        if isinstance(node, Mapping):
            name = node.get("name")
            if isinstance(name, str) and name:
                return strip_litellm_prefix(name)
        elif isinstance(node, str) and node:
            return strip_litellm_prefix(node)
    for row in run.scores:
        if not isinstance(row, Mapping):
            continue
        model = row.get("judge_model")
        if isinstance(model, str) and model:
            return strip_litellm_prefix(model)
    return ""


# ── Public API ──────────────────────────────────────────────────────


def push_run_dir(
    run_dir: str,
    *,
    project: str | None = None,
    evaluator_mode: EvaluatorMode = "both",
    eval_name: str | None = None,
    run_name: str | None = None,
    dataset_name: str | None = None,
    passing_when_true: Mapping[str, bool] | None = None,
    judge_threshold: float = 3.0,
    project_client: Any | None = None,
    dry_run: bool = False,
) -> PushResult | DryRunResult:
    """Load ``run_dir`` and push it to Foundry.

    ``project_client`` is injectable so tests can mock the SDK
    surface entirely. Production callers pass ``project`` (an ARM
    resource id or ``https://<account>.services.ai.azure.com/api/projects/<project>``
    endpoint URL) and the pipeline builds a client from
    :class:`~azure.identity.DefaultAzureCredential`.
    """
    return push_run(
        load_run(run_dir),
        project=project,
        evaluator_mode=evaluator_mode,
        eval_name=eval_name,
        run_name=run_name,
        dataset_name=dataset_name,
        passing_when_true=passing_when_true,
        judge_threshold=judge_threshold,
        project_client=project_client,
        dry_run=dry_run,
    )


def push_run(
    run: AssertRun,
    *,
    project: str | None = None,
    evaluator_mode: EvaluatorMode = "both",
    eval_name: str | None = None,
    run_name: str | None = None,
    dataset_name: str | None = None,
    passing_when_true: Mapping[str, bool] | None = None,
    judge_threshold: float = 3.0,
    project_client: Any | None = None,
    dry_run: bool = False,
) -> PushResult | DryRunResult:
    """Push an already-loaded :class:`AssertRun` to a Foundry project.

    See :func:`push_run_dir` for parameter semantics.
    """
    # Step 2: build evaluator specs (pure).
    evaluator_specs = build_evaluator_specs_for_run(run, mode=evaluator_mode)
    if not evaluator_specs:
        raise PushError(
            "Cannot push run: scores.jsonl has no scored dimensions. Run the "
            "judge stage on this run before publishing."
        )

    # Step 4: build rows + content hash (pure).
    directions = dict(passing_when_true or {})
    rows = build_dataset_rows(run, passing_when_true=directions)
    payload_bytes = rows_to_jsonl_bytes(rows)
    dataset_version = content_hash(payload_bytes)

    # Judge deployment name — needed for prompt-variant init_parameters.
    judge_deployment = resolve_judge_deployment(run)
    _requires_deployment = any(s.variant == "prompt" for s in evaluator_specs)
    if _requires_deployment and not judge_deployment:
        raise PushError(
            "Cannot push run with prompt-variant evaluators: judge model name "
            "is missing. Set default_model.name or pipeline.judge.model.name in "
            "config.yaml, or re-run the judge stage so scores.jsonl records "
            "the model that judged the run."
        )

    resolved_eval_name = eval_name or default_eval_name(run)
    resolved_run_name = run_name or default_run_name(run)
    resolved_dataset_name = dataset_name or default_dataset_name(run)

    if dry_run:
        return DryRunResult(
            eval_name=resolved_eval_name,
            run_name=resolved_run_name,
            dataset_name=resolved_dataset_name,
            dataset_version=dataset_version,
            dataset_row_count=len(rows),
            evaluator_specs=tuple(evaluator_specs),
            judge_deployment=judge_deployment,
            passing_when_true=directions,
        )

    # Real push. Build the SDK clients if not injected.
    client, owned_client = _resolve_project_client(project, project_client)
    try:
        return _push_with_client(
            run,
            client=client,
            evaluator_specs=evaluator_specs,
            payload_bytes=payload_bytes,
            dataset_version=dataset_version,
            row_count=len(rows),
            eval_name=resolved_eval_name,
            run_name=resolved_run_name,
            dataset_name=resolved_dataset_name,
            judge_deployment=judge_deployment,
            judge_threshold=judge_threshold,
        )
    finally:
        if owned_client:
            close = getattr(client, "close", None)
            if callable(close):
                close()


# ── Internals ───────────────────────────────────────────────────────


def _push_with_client(
    run: AssertRun,
    *,
    client: Any,
    evaluator_specs: Sequence[AssertEvaluatorSpec],
    payload_bytes: bytes,
    dataset_version: str,
    row_count: int,
    eval_name: str,
    run_name: str,
    dataset_name: str,
    judge_deployment: str,
    judge_threshold: float,
) -> PushResult:
    # Step 3: register evaluators (idempotent).
    evaluator_refs, reused_evaluators = _ensure_evaluators(
        client.beta.evaluators, evaluator_specs
    )

    # Step 5: upload dataset (content-addressed reuse).
    dataset_ref, reused_dataset = _ensure_dataset(
        client.datasets,
        name=dataset_name,
        version=dataset_version,
        payload_bytes=payload_bytes,
    )

    # Step 6 + 7: resolve eval by name; fail on testing_criteria drift.
    openai_client = client.get_openai_client()
    testing_criteria = _build_testing_criteria(
        evaluator_refs=evaluator_refs,
        evaluator_specs=evaluator_specs,
        judge_deployment=judge_deployment,
        judge_threshold=judge_threshold,
    )
    data_source_config = _build_data_source_config(evaluator_specs)

    eval_id, reused_eval = _ensure_eval(
        openai_client,
        name=eval_name,
        testing_criteria=testing_criteria,
        data_source_config=data_source_config,
        run_metadata=_eval_metadata(run, row_count=row_count),
    )

    # Step 8: create the eval run.
    run_id = _create_eval_run(
        openai_client,
        eval_id=eval_id,
        run_name=run_name,
        dataset_asset_id=dataset_ref.asset_id,
        run_metadata=_run_metadata(run, dataset_version=dataset_version),
    )

    return PushResult(
        eval_id=eval_id,
        run_id=run_id,
        evaluator_refs=tuple(evaluator_refs),
        dataset_ref=dataset_ref,
        reused_evaluators=tuple(reused_evaluators),
        reused_dataset=reused_dataset,
        reused_eval=reused_eval,
    )


# ── Step 3: evaluator registration ──────────────────────────────────


def _ensure_evaluators(
    evaluators_op: Any,
    specs: Sequence[AssertEvaluatorSpec],
) -> tuple[list[EvaluatorRef], list[str]]:
    """Register each spec unless the named+version already exists as an exact match.

    Foundry's evaluator name+version is the identity: name and
    version together identify one immutable definition. If the same
    ``assert-{dim}[/-rescore]`` at version ``"1"`` already exists in
    the catalog **and its definition fingerprints byte-identical to
    what we would send**, reuse it.

    We compare a stable fingerprint over the semantic fields of
    ``definition`` (see :func:`_definition_fingerprint`) rather than
    just the type. Any drift — old ASSERT v1 ``rubric`` shape, a
    change in ``code_text``, an edited prompt rubric, a widened
    ``data_schema``, or new ``init_parameters`` — flips the
    fingerprint and forces a ``delete_version`` +
    ``create_version``.

    Description text and display names are UI-only and are
    excluded from the fingerprint on purpose: a customer editing
    prose in their config shouldn't trigger a delete+recreate as
    long as the scoring behavior is unchanged.

    Callers who want a fresh registration can also delete the
    version in the Foundry UI before pushing.
    """
    refs: list[EvaluatorRef] = []
    reused: list[str] = []
    for spec in specs:
        name = spec.evaluator_name
        version = "1"
        expected_fingerprint = _definition_fingerprint(spec.evaluator_version)
        existing = _get_evaluator_version(evaluators_op, name=name, version=version)
        if existing is None:
            evaluators_op.create_version(name, spec.evaluator_version)
        elif _definition_fingerprint(existing) == expected_fingerprint:
            reused.append(name)
        else:
            # Definition has drifted — delete and re-register so
            # downstream eval-create doesn't run against a stale
            # schema, and so new eval runs pick up the current
            # grader logic / rubric.
            evaluators_op.delete_version(name, version)
            evaluators_op.create_version(name, spec.evaluator_version)
        refs.append(
            EvaluatorRef(
                dimension_id=spec.dimension_id,
                variant=spec.variant,
                evaluator_name=name,
                evaluator_version=version,
            )
        )
    return refs, reused


def _get_evaluator_version(
    evaluators_op: Any, *, name: str, version: str
) -> Any | None:
    """Return the SDK object for name/version, or ``None`` when not found."""
    try:
        return evaluators_op.get_version(name, version)
    except _resource_not_found_types():
        return None


def _definition_fingerprint(evaluator_version: Any) -> str:
    """Stable 12-char fingerprint of the semantic definition fields.

    Covers every field that changes what score a row receives:
    ``type``, ``code_text`` / ``prompt_text``, ``data_schema``,
    ``init_parameters``, and ``metrics``. Explicitly **excludes**
    UI-only fields like ``description`` and ``display_name`` — a
    customer editing rubric prose in their ASSERT config shouldn't
    force a delete+recreate as long as the underlying grader
    behavior is unchanged. (Rubric changes that affect the
    prompt-variant's ``prompt_text`` still flip the fingerprint
    because they mutate the actual grader body.)

    Works on both SDK model instances (returned by ``get_version``)
    and plain dicts (returned by test fakes) via :func:`_dict_get`.
    """
    definition = _dict_get(evaluator_version, "definition", {}) or {}
    canonical = {
        "type": str(_dict_get(definition, "type", "") or "").lower(),
        "code_text": _to_plain(_dict_get(definition, "code_text", None)),
        "prompt_text": _to_plain(_dict_get(definition, "prompt_text", None)),
        "data_schema": _to_plain(_dict_get(definition, "data_schema", {})),
        "init_parameters": _to_plain(_dict_get(definition, "init_parameters", {})),
        "metrics": _to_plain(_dict_get(definition, "metrics", {})),
    }
    payload = json.dumps(canonical, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _to_plain(value: Any) -> Any:
    """Recursively convert an SDK model or nested container to JSON-serializable form.

    SDK models expose ``as_dict()`` when available; otherwise we
    walk mappings and sequences by hand. Scalars pass through
    unchanged.
    """
    if value is None:
        return None
    if hasattr(value, "as_dict") and callable(value.as_dict):
        try:
            return _to_plain(value.as_dict())
        except Exception:
            pass
    if isinstance(value, Mapping):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(v) for v in value]
    return value


# ── Step 5: dataset registration ────────────────────────────────────


def _ensure_dataset(
    datasets_op: Any,
    *,
    name: str,
    version: str,
    payload_bytes: bytes,
) -> tuple[DatasetRef, bool]:
    """Reuse the existing dataset asset when the content hash matches."""
    try:
        existing = datasets_op.get(name, version)
    except _resource_not_found_types():
        existing = None

    if existing is not None:
        return _dataset_ref_from_sdk(existing, name=name, version=version), True

    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".jsonl", delete=False
    ) as tmp:
        tmp.write(payload_bytes)
        tmp_path = tmp.name
    try:
        uploaded = datasets_op.upload_file(
            name=name, version=version, file_path=tmp_path
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return _dataset_ref_from_sdk(uploaded, name=name, version=version), False


def _dataset_ref_from_sdk(sdk_obj: Any, *, name: str, version: str) -> DatasetRef:
    asset_id = getattr(sdk_obj, "id", None) or _dict_get(sdk_obj, "id", "")
    return DatasetRef(name=name, version=version, asset_id=str(asset_id or ""))


# ── Step 6 + 7: eval definition ─────────────────────────────────────


def _ensure_eval(
    openai_client: Any,
    *,
    name: str,
    testing_criteria: list[dict[str, Any]],
    data_source_config: dict[str, Any],
    run_metadata: dict[str, str],
) -> tuple[str, bool]:
    """Reuse the eval by name; fail loudly on testing_criteria drift."""
    existing = _find_eval_by_name(openai_client, name)
    if existing is not None:
        existing_id = _dict_get(existing, "id", "")
        _assert_testing_criteria_match(existing, testing_criteria, eval_name=name)
        return str(existing_id), True

    created = openai_client.evals.create(
        name=name,
        data_source_config=data_source_config,
        testing_criteria=testing_criteria,
        metadata=run_metadata,
    )
    return str(_dict_get(created, "id", "")), False


def _find_eval_by_name(openai_client: Any, name: str) -> Any | None:
    """Page the project's eval listing for the first entry matching ``name``.

    Foundry has no ``GET /evals?name=<...>`` filter, so we page.
    Realistic project sizes make this cheap; a follow-up may add a
    local cache if we grow to thousands of ASSERT evals per project.
    """
    for eval_obj in _iter_paged(openai_client.evals.list, order="desc"):
        if _dict_get(eval_obj, "name", None) == name:
            return eval_obj
    return None


def _assert_testing_criteria_match(
    existing_eval: Any,
    desired_testing_criteria: list[dict[str, Any]],
    *,
    eval_name: str,
) -> None:
    """Fail loudly when the existing eval's criteria don't match ours.

    Foundry's ``POST /evals/{id}`` (Update eval) only accepts name +
    metadata — testing_criteria cannot be patched. The safe default
    on drift is to refuse the push and instruct the user to
    disambiguate with ``--eval-name <suite>-v2`` (or delete the old
    eval in the Foundry UI).
    """
    existing_criteria = _dict_get(existing_eval, "testing_criteria", []) or []
    existing_names = sorted(
        _dict_get(c, "evaluator_name", "") for c in existing_criteria
    )
    desired_names = sorted(c["evaluator_name"] for c in desired_testing_criteria)
    if existing_names != desired_names:
        raise PushError(
            f"Eval {eval_name!r} already exists in the Foundry project with "
            f"different testing_criteria "
            f"(existing evaluators={existing_names}, requested={desired_names}). "
            f"Foundry does not allow patching testing_criteria after "
            f"creation. Fix: pass `--eval-name {eval_name}-v2` (or delete "
            f"the existing eval in the Foundry UI, then re-push)."
        )


# ── Step 8: eval run ────────────────────────────────────────────────


def _create_eval_run(
    openai_client: Any,
    *,
    eval_id: str,
    run_name: str,
    dataset_asset_id: str,
    run_metadata: dict[str, str],
) -> str:
    data_source = {
        "type": "jsonl",
        "source": {"type": "file_id", "id": dataset_asset_id},
    }
    created = openai_client.evals.runs.create(
        eval_id,
        data_source=data_source,
        name=run_name,
        metadata=run_metadata,
    )
    return str(_dict_get(created, "id", ""))


# ── testing_criteria + data_source_config construction ─────────────


def _build_testing_criteria(
    *,
    evaluator_refs: Sequence[EvaluatorRef],
    evaluator_specs: Sequence[AssertEvaluatorSpec],
    judge_deployment: str,
    judge_threshold: float,
) -> list[dict[str, Any]]:
    """Build the ``testing_criteria`` list for the eval definition."""
    specs_by_name = {s.evaluator_name: s for s in evaluator_specs}
    criteria: list[dict[str, Any]] = []
    for ref in evaluator_refs:
        spec = specs_by_name[ref.evaluator_name]
        init_params: dict[str, Any] = {}
        data_mapping: dict[str, str]
        if spec.variant == "code":
            # Code evaluator's data_schema declares `assert_scores` as a
            # top-level required field on the sandbox `item` object.
            # Foundry validates the mapping against the regex
            # ^\{\{(?:item|sample)\.[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*\}\}$
            # — the value must be `{{item.<field>}}` form, not `{{item}}`.
            data_mapping = {"assert_scores": "{{item.assert_scores}}"}
        else:
            init_params = {
                "deployment_name": judge_deployment,
                "threshold": judge_threshold,
            }
            data_mapping = {
                "query": "{{item.query}}",
                "response": "{{item.response}}",
            }
        criteria.append(
            {
                "type": _DATASET_EVALUATOR_TYPE,
                "name": (
                    ref.dimension_id
                    if spec.variant == "code"
                    else f"{ref.dimension_id}-rescore"
                ),
                "evaluator_name": ref.evaluator_name,
                "evaluator_version": ref.evaluator_version,
                "initialization_parameters": init_params,
                "data_mapping": data_mapping,
            }
        )
    return criteria


def _build_data_source_config(
    evaluator_specs: Sequence[AssertEvaluatorSpec],
) -> dict[str, Any]:
    """Foundry ``custom`` data source config declaring the row schema.

    Every row carries ``query`` + ``response`` + ``assert_scores`` +
    ``assert_reasons``. ``include_sample_schema`` is False because
    the eval reads from a registered dataset asset (file_id), not
    inline sample content.
    """
    dims = sorted({s.dimension_id for s in evaluator_specs})
    return {
        "type": "custom",
        "item_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "response": {"type": "string"},
                "assert_scores": {
                    "type": "object",
                    "properties": {d: {"type": "number"} for d in dims},
                    "required": dims,
                },
                "assert_reasons": {
                    "type": "object",
                    "properties": {d: {"type": "string"} for d in dims},
                    "required": [],
                },
            },
            "required": ["query", "response", "assert_scores"],
        },
        "include_sample_schema": False,
    }


# ── Metadata helpers ────────────────────────────────────────────────


def _eval_metadata(run: AssertRun, *, row_count: int) -> dict[str, str]:
    """Small (16-key, 512-char per value) metadata attached to the eval."""
    return _bounded_record(
        [
            ("assert.source", "assert-ai"),
            ("assert.suite_id", run.suite_id),
            ("assert.behavior_name", run.behavior_name),
            ("assert.category_count", str(run.behavior_category_count)),
            ("assert.row_count", str(row_count)),
        ]
    )


def _run_metadata(run: AssertRun, *, dataset_version: str) -> dict[str, str]:
    """Per-run metadata: enough to correlate a Foundry run to the ASSERT run on disk."""
    return _bounded_record(
        [
            ("assert.run_id", run.run_id),
            ("assert.run_dir", str(run.run_dir)),
            ("assert.dataset_version", dataset_version),
            ("assert.inference_config_hash", run.inference_config_hash or ""),
            ("assert.judge_config_hash", run.judge_config_hash or ""),
        ]
    )


def _bounded_record(entries: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Foundry Metadata: at most 16 keys, at most 512 chars per value."""
    result: dict[str, str] = {}
    for key, value in entries:
        if not value:
            continue
        text = str(value)
        if len(text) > 512:
            text = text[:511] + "…"
        result[key] = text
    if len(result) > 16:
        # This is a coding bug — the mapper's key set is bounded.
        raise PushError(f"Metadata record exceeded 16 keys ({len(result)}).")
    return result


# ── SDK client construction ─────────────────────────────────────────


def _resolve_project_client(
    project: str | None, injected: Any | None
) -> tuple[Any, bool]:
    """Return ``(client, owned)`` — build a fresh SDK client or reuse the injected one."""
    if injected is not None:
        return injected, False
    if not project:
        raise PushError(
            "Either `project_client` or `project` (endpoint URL / ARM id) is required."
        )
    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:  # pragma: no cover - covered by extras hint
        raise PushError(
            "The Foundry pipeline requires 'azure-ai-projects' and 'azure-identity'. "
            'Install with: pip install "assert-ai[foundry]"'
        ) from exc
    endpoint = _endpoint_from_project(project)
    client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    return client, True


def _endpoint_from_project(project: str) -> str:
    """Resolve ``project`` to the Foundry data-plane endpoint URL.

    Accepts:
    - the endpoint URL directly (``https://<account>.services.ai.azure.com/api/projects/<project>``);
    - the shorthand ``{account}/{project}``;
    - the full ARM resource ID
      (``/subscriptions/.../accounts/{account}/projects/{project}``).
    """
    project = project.strip()
    if project.startswith("https://"):
        return project.rstrip("/")

    account = ""
    project_name = ""

    if "/providers/" in project.lower():
        # ARM ID: extract account + project (case-insensitive segment names).
        segments = project.strip("/").split("/")
        account = _segment_after(segments, "accounts")
        project_name = _segment_after(segments, "projects")
    else:
        parts = [p for p in project.strip("/").split("/") if p]
        if len(parts) == 2:
            account, project_name = parts

    if not account or not project_name:
        raise PushError(
            f"Cannot resolve Foundry endpoint from project {project!r}. "
            "Expected one of: an endpoint URL "
            "(https://<account>.services.ai.azure.com/api/projects/<project>), "
            "the shorthand '<account>/<project>', or a Cognitive Services "
            "project ARM id (/subscriptions/.../accounts/<account>/projects/<project>)."
        )
    return (
        f"https://{account}.services.ai.azure.com/api/projects/{project_name}"
    )


def _segment_after(segments: Sequence[str], key: str) -> str:
    key_lower = key.lower()
    for i, seg in enumerate(segments):
        if seg.lower() == key_lower and i + 1 < len(segments):
            return segments[i + 1]
    return ""


# ── Small SDK-shape utilities ───────────────────────────────────────


def _dict_get(obj: Any, key: str, default: Any) -> Any:
    """Read ``key`` off an SDK model or plain dict.

    SDK models expose fields as attributes AND MutableMapping keys,
    but pagination iterators may return plain dicts in some paths.
    Uniform accessor keeps callers simple.
    """
    if hasattr(obj, key):
        value = getattr(obj, key, None)
        if value is not None:
            return value
    try:
        return obj[key]  # type: ignore[index]
    except (KeyError, TypeError, IndexError):
        return default


def _iter_paged(list_fn: Any, **kwargs: Any) -> Iterable[Any]:
    """Yield every item in an SDK pager, tolerating both paged + eager returns."""
    try:
        result = list_fn(**kwargs)
    except TypeError:
        # Some list_fns don't accept our kwargs — retry without.
        result = list_fn()
    if result is None:
        return
    yield from result


def _resource_not_found_types() -> tuple[type, ...]:
    """The exception classes we treat as "not registered yet".

    Constructed lazily so tests that don't touch the SDK still work
    on a base install.
    """
    types: list[type] = [KeyError]  # local fallback for tests using dict-backed mocks
    try:
        from azure.core.exceptions import ResourceNotFoundError

        types.append(ResourceNotFoundError)
    except ImportError:  # pragma: no cover
        pass
    try:
        from openai import NotFoundError

        types.append(NotFoundError)
    except ImportError:  # pragma: no cover
        pass
    return tuple(types)


__all__ = [
    "DATASET_NAME_PREFIX",
    "DatasetRef",
    "DryRunResult",
    "EVAL_NAME_PREFIX",
    "EvaluatorRef",
    "PushError",
    "PushResult",
    "RUN_NAME_PREFIX",
    "default_dataset_name",
    "default_eval_name",
    "default_run_name",
    "push_run",
    "push_run_dir",
    "resolve_judge_deployment",
    "strip_litellm_prefix",
]
