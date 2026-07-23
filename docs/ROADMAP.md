# Roadmap & status

> Living document: the plan, current status, and active next step. Newest status in
> `docs/SESSION_LOG.md`. Last updated: **2026-07-23** (Session 1).

## Objective

Use the PETSc **multi-agent AI system** to automatically produce a **verified PETSc
simulation of tokamak plasma** (fusion MHD), and turn the result into (1) a **US-RSE 2026
poster**, (2) an **Argonne summer-2026 intern presentation**, and (3) **documentation** —
demonstrating the proposal's thesis: automated, verification-driven, problem-to-solution
generation for PDE-based simulation science.

## Milestones

| # | Milestone | Status |
|---|---|---|
| 0 | Understand system; verify agents run on this box; scaffold + docs | ✅ Session 1 |
| 1 | Orchestration driver + artifact/provenance capture (`src/`) | ⬜ |
| 2 | Agent-generated **Grad–Shafranov / Solov'ev** PETSc solver that **compiles & runs** | ⬜ |
| 3 | **Verification**: manufactured-solution convergence (Solov'ev exact) + cross-check vs FreeGS | ⬜ |
| 4 | **Visualization/Analysis agent** — flux surfaces, q-profile, diagnostics from the run | ⬜ |
| 5 | Demonstrate the built-in **orchestrator** agent end-to-end (where feasible) | ⬜ |
| 6 | **Metrics** vs the proposal's decision gates (correctness, human-time, tokens/cost) | ⬜ |
| 7 | **US-RSE 2026 poster** (abstract from template + poster) | ⬜ |
| 8 | **Argonne intern presentation** (slides) | ⬜ |
| 9 | Stretch: harder physics (nonlinear pressure profiles; time-dependent/resistive MHD) | ⬜ |

## Physics ladder (agent-tractable → ambitious)

1. **Solov'ev Grad–Shafranov** (linear source, exact solution) — verification anchor.
2. **Nonlinear Grad–Shafranov** (realistic p(ψ), FF′(ψ)) via SNES — Picard/Newton.
3. **Shaped boundary / real machine** (D-shape, X-point) — cross-check vs `~/tokamak` FreeGS.
4. **Stretch:** time-dependent transport or reduced/resistive MHD (TS).

Each rung is validated by reproducing a known answer before climbing.

## Improvements to the multi-agent system (contribute upstream)

- `petscmcp.generateServer`: `python3.13` → `sys.executable` (portability).
- Code-generator server: make documentation/rag sub-servers **optional** (degrade to
  compile-run-only) so it works where docs/RAG aren't provisioned.
- Add a **Visualization & Analysis** MCP server (proposal's 4th execution agent).
- Add **persistent artifact memory** (structured run store the orchestrator can reuse).

## Deliverable notes

- **Poster** (`poster/`): abstract must follow `USRSE_2026_Posters_Submission_Template.docx`.
  Angle: "Automated problem-to-solution generation for a tokamak MHD equilibrium with a
  hierarchical multi-agent PETSc system." Lead with verification + human-effort reduction.
- **Slides** (`slides/`): Argonne intern audience — motivate fusion, show the agent
  pipeline, the generated code, the verified result, and the metrics.
