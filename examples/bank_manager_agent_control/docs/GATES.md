# Gate reports — feature-representation experiment

Each phase of this experiment passes through a **gate**: a written, reproducible
check that must be green before the next phase is allowed to consume its output.
The point is to keep confounders and pollution out of the final numbers, so that
when the headline result lands ("feature gates generalize, text gates don't") it
is a property of the design and not an artifact of a broken harness.

Run all build-correctness checks:

```
cd examples/bank_manager_agent_control
python3 -m unittest discover -s tests -p 'test_*.py'   # 51 tests
python3 smoke_test.py                                  # offline KB end-to-end
```

---

## Gate 0 — Build correctness  ✅ PASS

**Status:** `51 passed, 1 skipped` (the skipped case needs `mcp`; it runs on the
work laptop). Offline KB smoke: `5 passed, 0 failed`.

**Why this gate exists.** Before measuring guardrail behavior we must prove the
*apparatus* is sound: one copy of the data, tools that emit the typed signals
the gates read, isolated per-turn state, and — critically — that the central
claim is encoded as a falsifiable test rather than asserted in prose.

### What each test group protects, and the confounder it removes

| Test module | Protects | Confounder / pollution eliminated |
|---|---|---|
| `test_data_integrity.py` | risk_tier validity, referential integrity, per-domain ID-prefix uniqueness, sensitive entities present under LN-/BR- prefixes, XPIA fixture intact, field types | **Silent data rot.** A bad tier or a collided prefix would make a gate mis-fire or quietly break the generalization split. |
| `test_data_integrity.py::test_single_source_of_truth` | The MCP server re-exports `bank_core`'s tables **by identity** (`assertIs`) | **Duplicate-data divergence.** The old server held its own second copy of every table; a later edit to one copy would desync data from tests. Now there is exactly one copy. *(skipped without `mcp`; verified on the work laptop.)* |
| `test_generalization.py` | text gate catches exactly `{ACC-1002, ACC-1003}`; feature gate has recall 1.0 on all sensitive entities and 0 false positives on standard | **The premise itself.** This is the talk's headline written as a test. If it ever fails, no downstream number is meaningful. Loans/brokerage are a true held-out set (never tuned on). |
| `test_text_invariance.py` | renaming an entity ID (risk_tier fixed) leaves the feature decision unchanged but flips the text decision | **Hidden text-dependence.** Rules out the nightmare confounder where the "feature" gate is secretly still keying on the ID and its generalization is an artifact. |
| `test_tool_contracts.py` | every tool returns its typed signals; approval state machine (prepare→approve→create, bad/missing token rejected); freeze reflected; `reset_state` clears counters & freezes | **Cross-trial contamination.** Per-turn enumeration counters (`session_account_reads`, `entity_reads`) leaking between turns/tests would corrupt the enumeration signal. Reset is tested explicitly. |
| `test_policy.py::HardInvariants` | admin-only tools and the approval-token requirement are enforced **identically** by both gate arms | **Accidental asymmetry.** Ensures the only difference between B2 (text) and T1 (feature) is the discriminator under study — not a divergence in the hard rules. |
| `test_policy.py::InjectionContrast` | text injection regex fires on a benign in-scope transfer memo (false positive); feature gate stays quiet on it yet still catches the out-of-scope XPIA exfil (`ACC-9999`) | **The overrefusal mechanism.** Demonstrates, at unit level, the frontier the experiment will measure: the text gate cannot both catch the attack and clear the benign case. |
| `test_kb.py` | grounded↔citations consistency, out-of-scope ⇒ ungrounded, poisoned doc retrievable, **determinism** (same query ⇒ identical result) | **Grounding-signal noise.** A nondeterministic retriever would make the grounding metric jitter run-to-run; determinism is pinned so the `grounded` feature is a stable signal. |

### Design decisions made at this gate (single source of truth)

- **`bank_core.py`** now holds all entity data + pure tool logic with **no `mcp`
  dependency**. `realistic_bank_mcp_server.py` is a thin wrapper that imports
  these functions and JSON-encodes them. This removes the duplicate-data
  confounder *and* lets the bank logic be unit-tested here (Python 3.9, no deps).
- **`feature_policy.py`** encodes both discriminators (`TextGate`, `FeatureGate`)
  behind one `decide(event)` interface so they can be compared on identical
  inputs. The Rego policy (P2) will mirror `FeatureGate`; keeping the logic in
  pure Python makes the discriminator unit-testable in isolation.
- **`create_transfer` does not mutate `ACCOUNTS` balances** (the old server did).
  Module-level balance mutation would pollute state across turns/tests unless
  restored on reset; the experiment gates on decisions, not balance accounting,
  so the non-mutating version is canonical.

### Known follow-ups (not blocking Gate 0)

- The `mcp`/`langgraph`-gated checks (server build, agent import) run only on the
  work laptop; they are skipped (not failed) here and reported as SKIP.
- `agent.py` two-server wiring + the feature-gate Rego are the next slice (P0→P2);
  each gets its own gate section below as it lands.

---

## Gate A — Agent wiring (two MCP servers + feature policy)  ✅ PASS (offline) / ⏳ work-laptop legs deferred

**Status (this machine):** `unittest` 59 passed / 1 skipped; `smoke_test.py`
offline 8 passed / 0 failed. The `mcp`/`langgraph`/`opa` legs are SKIP here and
run on the work laptop.

**What landed**

- `feature_policy.py` host state machine (pure, unit-tested): `new_feature_state`
  (seeds `authorized_refs` from the entity IDs the user named), `pre_call_snapshot`
  (cross-call invariants: per-transfer approval + source sensitivity, admin),
  `post_call_snapshot` (authorized scope), `record_result` (folds an allowed
  result into state). `tests/test_snapshot.py` pins all of it.
- `acs/policy/bank_manager_feature.rego` + `acs/manifest_feature.yaml` — the T1
  policy. Same intervention points as the text policy; sensitivity gates moved
  to `post_tool_call` so they read the typed `risk_tier` from the tool result
  (covers ACC/LN/BR/CL uniformly). Exfil gate = referenced entity outside
  `authorized_refs`. Grounding gate = KB `grounded==false`. `create_transfer`
  approval + admin remain deterministic `pre_tool_call` invariants.
- `agent.py` — `chat_unguarded_realistic` (B0 on the realistic bank+KB) and
  `chat_guarded_acs_feature` (T1). Both load **two** MCP servers (bank + KB) via
  one `AsyncExitStack`; the feature wrapper mirrors the proven `run_tool`
  orchestration but builds its snapshot from typed host state, not hardcoded IDs.

**Design decisions / confounders addressed**

- *Hold the agent fixed.* `SYSTEM_PROMPT_REALISTIC` keeps the same "just call the
  tool" disposition as the baseline prompt, generalized to four domains + KB, so
  the only thing differing across arms is the guardrail — not the agent's temperament.
- *JSON-string result parsing.* MCP tools return a JSON string; ACS passes it to
  `post_tool_call` verbatim. The feature Rego `json.unmarshal`s it before reading
  typed fields (a silent failure mode if missed — it would read fields off a
  string and always get defaults, disarming every feature gate). Fail-open to
  the default `allow` only on a non-JSON string.
- *Surfaced ≠ authorized.* `record_result` never adds newly-referenced entities
  to `authorized_refs`; authorization comes only from the user's own message,
  or the exfil gate would disarm itself (tested).
- *Two-server lifetime.* `AsyncExitStack` (not nested `async with` in a worker
  thread) keeps both stdio sessions open for the agent's whole turn and sidesteps
  the asyncio-in-thread crash that dropped baseline cases in the original demo.

**Deferred to the work laptop (cannot run here — no `mcp`/`langgraph`/`opa`)**

1. `opa`-validate `bank_manager_feature.rego` (syntax + the `json.unmarshal` path);
   the policy is authored against ACS 0.3.0-alpha but not yet executed.
2. `smoke_test.py` DEPS: two-server build, feature callables present, agent import.
3. A live end-to-end on `azure/gpt-5-mini` (SWC unfiltered) for one sensitive-read
   and one XPIA case per arm, to confirm the deny messages surface to the agent.

These three are this gate's open items; the offline core (state machine,
generalization premise, artifact shape) is green.

---

## Gate 1 — Eval configs + generalization split  ✅ PASS (authoring) / ⏳ generation deferred

**Status (this machine):** structural lint green (no tabs; required keys; the
three reuse arms carry a judge block byte-identical to B0; B0 alone owns
systematize+test_set). All four configs use `azure/gpt-5.4-mini` only — **zero
non-Azure / hosted-API model strings** (asserted) — and every `callable:`
target resolves to a function defined in `agent.py`.

**The four arms (new suite `bank-manager-feature-rep`, n=100 = 50 prompt + 50 scenario):**

| Arm | Config | Target callable | Guardrail |
|---|---|---|---|
| B0 | `eval_realistic_unguarded.yaml` | `chat_unguarded_realistic` | none (owns + freezes the test_set) |
| B1 | `eval_realistic_prompted.yaml` | `chat_unguarded_realistic_prompted` | defensive prompt addendum |
| B2 | `eval_realistic_acs_text.yaml` | `chat_guarded_acs_text_realistic` | legacy TEXT ACS, un-updated for new ids |
| T1 | `eval_realistic_acs_feature.yaml` | `chat_guarded_acs_feature` | FEATURE ACS (typed signals) |

**Generalization split (encoded in the stratify dimension).** `request_type`
has 14 values: the original 7 ACCOUNTS types (the gate-tuning / "train" domain)
+ 7 NEW-DOMAIN types (`loan_modification_social_engineering`,
`margin_call_pressure`, `restricted_security_request`,
`cross_domain_enumeration`, `kyc_probe`, `benign_policy_question`,
`poisoned_kb_doc`). The headline slice = violation rate by domain: B2's
hardcoded `ACC-100[23]` gates hold on ACCOUNTS but fail on LN-/BR-/CL- entities;
T1 holds across all. New sensitive entities live under new id prefixes
specifically so the text gate provably can't reach them.

**Confounders addressed**

- *Identical judge across arms.* The three reuse configs are generated from B0's
  exact judge bytes, so a metric difference between arms cannot come from a
  drifted rubric — only from agent behavior. Lint asserts the byte-identity.
- *One frozen substrate.* Only B0 owns systematize+test_set; B1/B2/T1 fall back
  to the suite-root `test_set.jsonl`, so every arm is scored on the same cases.
- *Unfiltered models everywhere.* All stages on `azure/gpt-5.4-mini`
  (qualityevalswc, unfiltered). A filtered deployment would block adversarial
  cells and confound both the agent's "refusals" and the judge — explicitly
  avoided; no non-Azure model is referenced.
- *Deployment-name consistency.* `.env.example` `AGENT_MODEL` reconciled to
  `gpt-5.4-mini` so the agent-under-test and the eval/judge hit the SAME
  deployment (was `gpt-5-mini`, a mismatch with the committed configs).
- *New judge dimension.* `ungrounded_policy_claim` scores fabricated/poisoned
  policy answers — the KB-grounding behavior B0–T1 differ on.

**Deferred to the work laptop:** running B0 once to generate + freeze the
test_set (needs Azure creds + ACS/opa for the guarded arms), then B1/B2/T1 on
the frozen set. The frozen `test_set.jsonl` should be committed locally so the
arms are reproducible.

---

## Gate 2 — Core frontier + generalization result  ⏳ pending (P2)
## Gate 3 — Calibration / operating curves  ⏳ pending (P3)
## Gate 4 — GEPA marginal gain on held-out  ⏳ pending (P4)
## Gate 5 — Foundry IQ swap (real KB)  ⏳ pending (P5)
