# System of multiple AI agents to automate the simulation workflow in plasma physics (application in nuclear fusion energy). 

Automatically generate, verify, and run a **PETSc simulation of tokamak plasma** (nuclear
fusion MHD) using the PETSc **multi-agent AI system**
([`gitlab.com/petsc/petsc_mcp_servers`](https://gitlab.com/petsc/petsc_mcp_servers)), then
turn the result into a **US-RSE 2026 poster**, an **Argonne intern presentation**, and
documentation.

This realizes the stretch goal of the design proposal *Automated Problem-to-Solution
Generation for PDE-Based Simulation Science* (McInnes et al., DE-FOA-0003612): a
hierarchical, verification-driven, multi-agent system that turns a plain-language problem
description into correct, runnable simulation code — here, the tokamak **Grad–Shafranov**
MHD equilibrium.

## Layout

```
docs/        ENVIRONMENT.md · ARCHITECTURE.md · ROADMAP.md · SESSION_LOG.md
src/         orchestration driver + tokamak-specific code (WIP)
artifacts/   captured agent outputs per run (models, decisions, code, run logs)
poster/      US-RSE 2026 poster + abstract (WIP)
slides/      Argonne summer-2026 intern presentation (WIP)
```

## Start here

- **What is this / how does it work** → `docs/ARCHITECTURE.md`
- **How to run it on this machine** → `docs/ENVIRONMENT.md`
- **How to run the workflow end to end** → `docs/USAGE.md`
- **Changes we made to the multi-agent system** → `docs/AGENT_SYSTEM_CHANGES.md` (+ `patches/`)
- **Where are we / what's next** → `docs/SESSION_LOG.md` (newest at bottom)
- **The plan** → `docs/ROADMAP.md`

## Status

**Session 1 (2026-07-23): end-to-end success.** From the plain-language prompt *"the
Grad–Shafranov equilibrium for the plasma in a tokamak,"* the multi-agent pipeline
(Modeling → Numerical Analysis → HPC Code Generation, on ANL Argo / Opus 4.8) produced a
**267-line PETSc `DMDA`+`SNES` solver** that **compiled and ran on 1 and 4 MPI ranks with
no human edits**, and it **verifies at second order** (observed order **p = 2.00**;
max-norm error 2.1×10⁻⁴ at 65×65 → 1.3×10⁻⁵ at 257×257; `CONVERGED_FNORM_RELATIVE`).
Canonical run: `artifacts/run-20260723-113024/`. Figures in `figures/`, decision-gate
metrics in `artifacts/<run>/metrics.md`, draft poster abstract + 10-slide deck in
`poster/` and `slides/`. See `docs/SESSION_LOG.md` for what's next.

## Related work on this machine (not part of this repository)

`~/tokamak` — a commercial-agent-built (Claude Code, **not** via the MCP agents) validated tokamak
stack (Grad–Shafranov via FreeGS, Vlasov–Poisson PIC, C Landau collision operator, single
GPU). Used here only as a **physics cross-check** reference.
