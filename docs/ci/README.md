# CI safety gate

Use [`responsibleai/assert-action`](https://github.com/responsibleai/assert-action) to run ASSERT in pull requests and fail on safety regressions.

The fastest setup path is the action's agent bootstrap:

```text
read https://raw.githubusercontent.com/responsibleai/assert-action/main/ONBOARD.md
```

Generated workflows should call `responsibleai/assert-action@v1`. Keep provider credentials in CI secrets and reference environment variable names only.
