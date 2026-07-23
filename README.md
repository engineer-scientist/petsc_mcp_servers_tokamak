# PETSc multi-agent tokamak-plasma simulation

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
- **Where are we / what's next** → `docs/SESSION_LOG.md` (newest at bottom)
- **The plan** → `docs/ROADMAP.md`

## Status

Session 1 (2026-07-23): system understood; the Math-Modeling and Numerical-Analysis agents
verified producing a correct Grad–Shafranov model and discretization choice against ANL
Argo; repo scaffolded. Next: the orchestration driver + an agent-generated, verified
Grad–Shafranov solver. See `docs/SESSION_LOG.md`.

## Related work on this machine (not part of this repo)

`~/tokamak` — a hand-built (Claude Code, **not** via the MCP agents) validated tokamak
stack (Grad–Shafranov via FreeGS, Vlasov–Poisson PIC, C Landau collision operator, single
GPU). Used here only as a **physics cross-check** reference.
