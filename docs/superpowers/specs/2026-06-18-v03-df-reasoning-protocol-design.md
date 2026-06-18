# v0.3 DF Reasoning Protocol Design

## Goal

Upgrade the skill from a paper-grounded formula library into a disciplined derivation assistant. Registered v0.2 models remain reusable; near and new models must expose an event-based DF evidence chain; unsupported models are rejected.

## Architecture

The intake classifier is the gate. It emits `KNOWN_MODEL`, `NEAR_MODEL`, `NEW_MODEL`, `INCOMPLETE`, or `UNSUPPORTED`. Only registered exact matches may bypass a fresh event derivation. Missing comparator events stop before a final transfer function.

`df_protocol_case.py` turns a complete intake into a structured v0.3 case. It preserves the event equation, movable edge, edge sensitivity, DF relation, provenance, and validation status. `df_protocol_checker.py` checks this evidence contract in JSON or Markdown. It does not claim that a physically incorrect equation is correct.

## Required behavior

- Keep the four v0.2 registered models and their existing algebra path unchanged.
- Treat average-model-as-DF, DCM, pulse skipping, burst, nonlinear limiting, and multiphase overlap as unsupported.
- Require `F(x,u,t)=0`, an equivalent `delta_t=-delta_F/Fdot`, and a stated DF source for all protocol-derived cases.
- Default every new protocol derivation to `PROTOCOL_DERIVED_UNVERIFIED` / `UNVERIFIED_NEW_DF_MODEL`.
- Require `df_source`, `event_equation`, and `valid_frequency` for user-supplied coefficients.
- Preserve paper provenance separately from adapters, paper-inspired derivations, invented models, and user-supplied data.

## User interaction

The user-facing intake asks only five questions: target transfer function, operating/control mode, switching events, comparator inputs, and parameters. A ten-area checklist remains internal and causes focused missing-information requests.

## Verification

Tests cover classifier paths, protocol-case construction, report rendering, checker failure codes, CLI behavior, and all v0.2 regressions. Static forward scenarios verify the skill's prescribed behavior. Actual agent behavior and switching-simulation agreement remain explicitly unverified unless separately run.

## Non-goals

No arbitrary Buck support, DCM, multiphase overlap model, pulse skipping/burst model, circuit-image recognition, SPICE-to-DF synthesis, or verified claim for an AI-generated formula.
