# Roadmap & status

> Living document: the plan, current status, and active next step. Newest status in
> `docs/SESSION_LOG.md`. Last updated: **2026-08-05** (Session 6).
>
> **Session 5 (2026-08-05): milestone 9 DONE** — shaped equilibria (ITER, NSTX, X-point)
> agent-generated + verified (p = 2.00) with q-profiles cross-checked vs FreeGS.
> **Session 6 (2026-08-05): poster + abstract updated** — poster redesigned around the
> milestone-9 results + the multi-agent architecture diagram + institution logos, 4 authors,
> new title; abstract updated with the shaped-equilibria paragraph. **Remaining: export the
> EasyChair abstract PDF, add the 2 new authors to the abstract (need emails/ORCIDs), push.**

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
| 1 | Orchestration driver + artifact/provenance capture (`src/`) | ✅ Session 1 |
| 2 | Agent-generated **Grad–Shafranov** PETSc solver that **compiles & runs** | ✅ Session 1 (DMDA+SNES, 1&4 ranks) |
| 3 | **Verification**: manufactured-solution convergence | ✅ Session 1 (**p = 2.00**) |
| 4 | Post-processing figures (convergence, flux surfaces) | ✅ Session 1 · q-profile + shaped ✅ Session 5 |
| 5 | Demonstrate the built-in **orchestrator** agent end-to-end (where feasible) | ✅ Session 2 (DMPLEX+PetscFE, 225 DOFs; +upstream cntlimit fix) |
| 6 | **Metrics** vs the proposal's decision gates (correctness, human-time, tokens/cost) | ✅ Session 1 (`metrics.md`) |
| 7 | **US-RSE 2026 poster** — abstract ✅ (md+docx, incl. shaped results) · poster PPTX/PDF/PNG ✅ (redesigned Session 6: milestone-9 results + agent-architecture diagram + logos + 4 authors + new title) · EasyChair abstract PDF ⬜ · add 2 new authors to abstract ⬜ (need emails/ORCIDs) | 🟡 |
| 8 | **Argonne intern presentation** (slides) | ✅ **Presented at ANL intern event 2026-07-29** (13 slides on official ANL template) |
| 9 | Real-machine shaping (Solov'ev/Cerfon–Freidberg D-shape + X-point, q-profile) | ✅ Session 5 (ITER + NSTX + X-point double-null; **p = 2.00** all three; q-profile cross-checked vs FreeGS to <0.2%) |
| 10 | Stretch: harder physics (nonlinear profiles; time-dependent/resistive MHD) | ⬜ |

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
