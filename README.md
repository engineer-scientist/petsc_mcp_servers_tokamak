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
docs/        ARCHITECTURE · ENVIRONMENT · USAGE · VERIFICATION · AGENT_SYSTEM_CHANGES · ROADMAP · SESSION_LOG
src/         orchestration driver + verification, metrics, and shaped-equilibrium tooling
artifacts/   captured agent outputs per run (models, decisions, code, transcripts, run logs); LATEST → newest run
figures/     convergence, flux-surface, shaped-equilibria, and q-profile plots
patches/     upstream fixes to petsc_mcp_servers, as portable git-am patches (0001–0004)
poster/      US-RSE 2026 poster + abstract (abstract submitted; poster buildout ongoing)
slides/      Argonne summer-2026 intern presentation (presented 2026-07-29)
```

## Start here

- **What is this / how does it work** → `docs/ARCHITECTURE.md`
- **How to run it on this machine** → `docs/ENVIRONMENT.md`
- **How to run the workflow end to end** → `docs/USAGE.md`
- **How results are verified** → `docs/VERIFICATION.md`
- **Changes we made to the multi-agent system** → `docs/AGENT_SYSTEM_CHANGES.md` (+ `patches/`)
- **Where are we / what's next** → `docs/SESSION_LOG.md` (newest at bottom)
- **The plan** → `docs/ROADMAP.md`

## Status

**Current — through Session 6 (2026-08-05); `docs/SESSION_LOG.md` is the running log.**
The multi-agent pipeline (Mathematical Modeling → Numerical Analysis → HPC Code
Generation, on ANL Argo / Claude Opus 4.8) — driven by a project-owned orchestration
driver that records every intermediate artifact with full provenance — now generates
**verified** PETSc solvers for the tokamak **Grad–Shafranov** MHD equilibrium, from a
manufactured-solution anchor to **shaped, real-machine equilibria**. The engineering
thesis: **verification, not the model's confidence, decides acceptance**, and the human
RSE effort is *relocated* — into the orchestration, verification harness, provenance
store, and upstream guardrails — not eliminated.

**What the pipeline has produced**

- **Grad–Shafranov solver — Session 1.** From the prompt *"the Grad–Shafranov equilibrium
  for the plasma in a tokamak,"* the agents produced a **267-line PETSc `DMDA`+`SNES`
  solver** (true Jacobian, ghosted residual, built-in manufactured-solution check) that
  compiled and ran on **1 and 4 MPI ranks** as generated, and **verifies at second order**
  (**p = 2.00**; max-norm error 2.1×10⁻⁴ at 65×65 → 1.3×10⁻⁵ at 257×257;
  `CONVERGED_FNORM_RELATIVE`). Canonical run: `artifacts/run-20260723-113024/`.
- **Built-in orchestrator demo — Session 2.** Ran the shipped `orchestrator_mcp_server`
  end-to-end on the same problem → a **DMPLEX + PetscFE** solver that converged. Its first
  run tripped a shipped hard-coded iteration cap that **mislabeled a successful run as a
  failure** — a concrete guardrail failure we diagnosed and fixed upstream. Runs in
  `artifacts/orchestrator-20260724{,-fixed}/`.
- **Shaped, real-machine equilibria — Session 5 (milestone 9).** Using the analytic
  **Cerfon–Freidberg Solov'ev** solution as an exact benchmark, one agent-generated,
  parameterized solver reproduces **three shaped equilibria** — ITER-like D-shape,
  NSTX-like spherical, and a diverted **double-null with magnetic X-points** — each
  **verified at p = 2.00** on 1 and 4 ranks. The safety-factor profile q(ψ) of each is
  **cross-checked against the independent FreeGS code to < 0.2 %** on identical fields.
  Latest run: `artifacts/run-20260805-155724/` (= `artifacts/LATEST`). Figures in
  `figures/`; per-run decision-gate metrics in `artifacts/<run>/metrics.md`.

**Guardrail & robustness fixes contributed upstream.** Six documented fixes across three
files of `petsc_mcp_servers`, packaged as portable patches (`patches/0001–0004`), let the
agents run correctly on this shared compute node — including the iteration-cap fix that
stops a genuinely successful run from being reported as a failure. Full before/after:
`docs/AGENT_SYSTEM_CHANGES.md`.

**Deliverables**

- **Poster + abstract** (`poster/`) — the USRSE'26 abstract was finalized and exported for
  EasyChair (**2026-08-07**); the poster is redesigned around the shaped-equilibria
  results, the multi-agent architecture diagram, and institution logos. Per reviewer
  feedback (J. Zhang, L. C. McInnes), the poster is being reoriented toward the
  **research-software-engineering** story — orchestration, verification, and guardrails,
  plus a *succeed-vs-fail / how-we-harden-it* analysis — rather than a "no human edits"
  narrative; that buildout is the poster's focus over the coming weeks.
- **Slides** (`slides/`) — a 13-slide deck on the official Argonne template, **presented at
  the ANL summer-intern event on 2026-07-29**.

**What's next.** See `docs/SESSION_LOG.md` (newest at bottom) and `docs/ROADMAP.md`: build
out the poster's succeed/fail + guardrails analysis and harder-physics cases (nonlinear
profiles; time-dependent / resistive MHD), then push both repos upstream.

## Related work (not part of this repository)

`https://github.com/engineer-scientist/tokamak` — a commercial-agent-built (Claude Code, **not** via the MCP agents) validated tokamak stack (Grad–Shafranov via FreeGS, Vlasov–Poisson PIC, C Landau collision operator, single GPU). Used here only as a **physics cross-check** reference.
