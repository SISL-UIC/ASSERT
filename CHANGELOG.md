# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `pipeline.judge.concurrency`: pin how many transcripts the judge scores in parallel. See `docs/config/schema.md`.
- ACS guardrail adapter (`assert-ai[acs]` extra): turn a completed run's findings into a deployable Agent Control Specification policy via `assert-ai acs generate`, validate it against known-bad examples with `assert-ai acs validate`, and re-run a target guarded with the `guard_target` Python API. See `docs/guides/securing-agents-with-acs.md`.
- `assert-ai acs eval-config`: generate a small ASSERT config from an existing ACS manifest for regression/sanity checking an already-guarded target without requiring ACS runtime dependencies.

### Changed

- The judge stage no longer inherits a low `pipeline.inference.concurrency`. That setting exists to protect targets that can't be driven in parallel; the judge only scores transcripts already written to `inference_set.jsonl`, so it now defaults to `max(pipeline.inference.concurrency, 10) // max(judge.n, 1)`. Configs that pin `pipeline.inference.concurrency` below 10 will see the judge stage run faster and issue more concurrent judge-model calls. Set `pipeline.judge.concurrency` to restore the previous fan-out if your judge model shares a rate limit or deployment with your target. The effective value is logged when the judge stage starts.

### Fixed

[Unreleased]: https://github.com/responsibleai/ASSERT/commits/main
