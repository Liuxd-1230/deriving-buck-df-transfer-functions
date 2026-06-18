# v0.3 DF Reasoning Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a circuit-intake gate, event-based DF protocol cases, a protocol checker, paper proof skeletons, and honest v0.3 validation without regressing v0.2 models.

**Architecture:** Three focused Python modules handle classification, protocol-case construction/reporting, and evidence checking. The existing SymPy CLI delegates new commands to those modules while retaining the v0.2 algebra path.

**Tech Stack:** Python standard library, SymPy, unittest, Markdown and JSON fixtures.

---

### Task 1: Classification gate

**Files:** `tests/test_model_classifier.py`, `scripts/df_model_classifier.py`

- [ ] Write tests for known, near, new, incomplete, and unsupported classifications.
- [ ] Run the tests and confirm imports/behaviors fail before implementation.
- [ ] Implement deterministic structured-field classification and focused missing-field output.
- [ ] Re-run the classifier tests.

### Task 2: Protocol case and report

**Files:** `tests/test_protocol_case.py`, `scripts/df_protocol_case.py`

- [ ] Write tests requiring event equation, movable edge, edge perturbation, DF provenance, and unverified status.
- [ ] Confirm the tests fail before implementation.
- [ ] Implement case construction, custom-coefficient guards, and Markdown report rendering.
- [ ] Re-run the protocol-case tests.

### Task 3: Protocol checker

**Files:** `tests/test_protocol_checker.py`, `tests/protocol_failures/*`, `scripts/df_protocol_checker.py`

- [ ] Write JSON and Markdown tests for every required pass/fail/warning code.
- [ ] Confirm the tests fail before implementation.
- [ ] Implement ordered evidence checks and CLI exit behavior.
- [ ] Re-run checker tests and fixtures.

### Task 4: CLI integration

**Files:** `tests/test_v03_cli.py`, `scripts/df_buck_sympy.py`

- [ ] Write failing subprocess tests for `classify`, `make-protocol-case`, and v0.3 `derive`.
- [ ] Add command parsers and delegate to the focused modules.
- [ ] Run new and existing CLI tests.

### Task 5: Skill knowledge and examples

**Files:** `SKILL.md`, `references/*.md`, `references/paper-proof-skeletons/*.md`, `examples/*`

- [ ] Add contract tests that scan for the stop rules and validation labels.
- [ ] Write the two-layer intake, 12-step protocol, classification, schema, validation, unsupported-case references, and five proof skeletons.
- [ ] Add known, missing-event, near-model, unsupported, and derivation-template examples.
- [ ] Run the contract tests.

### Task 6: Validation and publication

**Files:** `VALIDATION.md`

- [ ] Run all v0.2 and v0.3 unit tests, benchmarks, checker fixtures, and skill validation.
- [ ] Record exact evidence and unresolved switching/agent-forward validation honestly.
- [ ] Review the diff against all acceptance criteria.
- [ ] Commit, push the feature branch, and open a draft pull request.
