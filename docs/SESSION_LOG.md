# Session log

> Append-only, newest session at the bottom. Each session records: what was done,
> what was verified, and the **exact next step** so any future session resumes cleanly.
> This is the primary "where are we?" document.

---

## Session 1 — 2026-07-23

**Goal.** Understand the multi-agent system, prove it can drive a tokamak PETSc
simulation on this machine, scaffold the project, and plan the deliverables
(US-RSE 2026 poster, Argonne intern presentation, documentation).

**Done.**
- Read the design proposal PDF and mapped its 3-layer hierarchy to the concrete MCP
  servers (see `docs/ARCHITECTURE.md`).
- Inventoried `petsc_mcp_servers`, the PETSc builds, and the reference physics in
  `~/tokamak`. Documented the runtime (see `docs/ENVIRONMENT.md`).
- **Verified the pipeline works on this box (against ANL Argo, nested `claude`):**
  1. `claude_agent_sdk` ↔ Argo (`claudeopus48`) round-trip → returns `PONG`.
  2. **Math Modeling agent** on "Grad-Shafranov equilibrium for tokamak plasma"
     → name = *Grad-Shafranov equation*, time-independent, correct strong+weak form,
     plus MathJax HTML and FEniCS UFL. (Source term `−μ₀R² p′ − F F′` correct.)
  3. **Numerical Analysis agent** on the GS spec → `{grid: unstructured-grid,
     discretization: finite-element}` → `DMPLEX`; nonlinear → `SNES`. Sensible.
  4. compile/run agent: verified in the **prior** session (`mcp_stage1_test.py`):
     create file → `make` (good) → run → `make` (broken) captures compiler stderr.
- Scaffolded this repo: `docs/ src/ artifacts/ poster/ slides/`, git init, remote set
  to `github.com/engineer-scientist/petsc_mcp_servers_tokamak`.

**Not yet done / open items.**
- HPC **Code Generation agent** not yet run this session (needs compile/run; its
  built-in config also references documentation+rag which are unavailable here — must be
  run compile-run-only or the server made to degrade gracefully).
- No orchestration driver written yet.
- No simulation generated/run/verified yet.
- Poster, slides, and top-level docs still to produce (from real results).

**Decisions taken (defaults; revisit if needed).**
- Physics target = **Grad–Shafranov MHD equilibrium**, starting with the **Solov'ev**
  case (closed-form exact solution → manufactured-solution convergence test).
- Orchestration = **project-owned artifact-logging driver** calling the real agents,
  plus a demo of the built-in `orchestrator` where feasible.
- Keep `petsc_mcp_servers` improvements (e.g. `python3.13`→`sys.executable`, graceful
  code-gen degradation, a Visualization/Analysis agent) as clearly-marked patches so
  they can be contributed upstream.

**EXACT NEXT STEP (start here next session).**
> Write `src/orchestrate_tokamak.py`: a driver that (a) calls Math Modeling → Numerical
> Analysis → Code Gen for the Grad–Shafranov/Solov'ev problem, (b) saves each structured
> artifact under `artifacts/<run-id>/`, (c) compiles+runs the generated PETSc C via the
> compile/run agent, (d) verifies against the Solov'ev exact solution. First get the
> **Code Generation agent** to emit a compiling PETSc program (compile-run-only mode).

**Reproduce Session-1 smoke tests.**
```bash
cd /home/sarthak.sharma/petsc_mcp_servers
P=/home/sarthak.sharma/.venvs/mcp-test/bin/python
env PYTHONPATH=$PWD $P -c "import asyncio,pde_modeling_mcp_server as m; \
  print(asyncio.run(m.generate_model_async('Grad-Shafranov equilibrium for tokamak plasma')).get('name'))"
```
