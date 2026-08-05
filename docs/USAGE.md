# Usage — running the workflow end to end

How to reproduce the agent-generated, verified tokamak Grad–Shafranov simulation.
See `docs/ENVIRONMENT.md` for the machine setup and `docs/ARCHITECTURE.md` for what the
agents are.

## Prerequisites (already true on this node)

- MCP-stack venv: `/home/sarthak.sharma/.venvs/mcp-test/bin/python`
- Multi-agent system: `/home/sarthak.sharma/petsc_mcp_servers` (on branch
  `tokamak-improvements`, which contains our portability/robustness fixes)
- PETSc: `~/petsc` with `PETSC_ARCH=arch-linux-c-opt`
- ANL Argo reachable (auto-configured by importing `petscmcp`)

Convenience:

```bash
export MCP=/home/sarthak.sharma/petsc_mcp_servers
export PYV=/home/sarthak.sharma/.venvs/mcp-test/bin/python
export PY3=/usr/bin/python3            # has numpy + matplotlib for figures
```

## 1. Generate the simulation (the multi-agent pipeline)

Drives Mathematical Modeling → Numerical Analysis → HPC Code Generation, saving every
structured artifact under `artifacts/<run-id>/` with a `manifest.json` (provenance).

```bash
cd /home/sarthak.sharma/petsc_mcp_servers_tokamak
env PYTHONPATH=$MCP $PYV src/orchestrate_tokamak.py --stages model,na,codegen
```

Options:
- `--stages model,na,codegen` — subset/order of stages to run (default all).
- `--resume run-YYYYmmdd-HHMMSS` — continue a run; completed stages are skipped
  (a stage is "done" if its marker artifact exists, so a crash never re-spends an LLM call).
- `--force` — re-run stages even if cached.

Artifacts produced per run (`artifacts/<run-id>/`):
`manifest.json` (provenance + per-stage status/timing), `model.{json,tex,html}`,
`model_ufl.py`, `model_full.md`, `na.json`, `grad_shafranov.c` (the generated solver),
`codegen.json`, `codegen_output.txt`. `artifacts/LATEST` names the most recent run.

## 2. Verify + post-process

Builds the generated solver, runs it on a grid ladder, measures the observed order of
accuracy against the manufactured exact solution, and writes figures.

```bash
env PETSC_DIR=$HOME/petsc PETSC_ARCH=arch-linux-c-opt \
    $PY3 src/verify_tokamak.py                 # uses artifacts/LATEST
# or: ... src/verify_tokamak.py --run run-YYYYmmdd-HHMMSS --sizes 33 65 129 257
```

Outputs: `figures/gs_convergence.png`, `figures/gs_flux_surfaces.png`,
`figures/gs_verification.json`, and `artifacts/<run>/verification.json`.
Use `--show` once to print raw solver output if the error-parsing needs calibrating.

## 3. Decision-gate metrics

```bash
$PY3 src/collect_metrics.py                     # uses artifacts/LATEST
```

Writes `artifacts/<run>/metrics.json` and `metrics.md` (correctness / efficiency /
human-effort table for the poster and slides).

## 4. (Optional) the built-in orchestrator agent

A faithfulness demo of the shipped LLM orchestrator driving the same servers, where an inner
Claude decides the sequence itself (rather than our Python driver doing it):

```bash
cd $MCP                                  # branch tokamak-improvements
env PYTHONPATH=$MCP PETSC_MCP_SERVERS_STDIO=True $PYV -u -c \
 "import asyncio, orchestrator_mcp_server as o; \
  print(asyncio.run(o.orchestrate_async('the Grad-Shafranov equilibrium for a tokamak plasma')))"
```

Success prints `I have completed the orchestration` and returns `{}` (an empty results dict;
a `{'failure_message': ...}` return means it gave up). It takes ~10–13 min: it nests deeply
(orchestrator → inner Claude → 4 stdio sub-servers, and the code generator spawns yet another
Claude). Ran end to end on 2026-07-24 — the agent independently produced a **DMPLEX + PetscFE**
Grad–Shafranov (Solov'ev) solver that compiled and ran (`||psi||_2 = 2.04156`, 225 DOFs).
Captured under `artifacts/orchestrator-20260724-fixed/` (and the as-shipped run that exposed
the iteration-cap bug under `artifacts/orchestrator-20260724/`). See those dirs' `README.md`
and `docs/AGENT_SYSTEM_CHANGES.md` change #6.

> Requires the orchestrator cap fix (change #6); an unpatched clone will report a false
> "Too many iterations" failure right after the code compiles. Apply `patches/0004-*.patch`
> or use branch `tokamak-improvements`.

## 5. Shaped, real-machine equilibria (milestone 9)

A second problem type generates + verifies a **physically shaped** Grad–Shafranov equilibrium
(D-shape / X-point) using the **Cerfon–Freidberg analytic Solov'ev** solution as the exact
answer — a real-machine equilibrium that is *still* a closed-form solution, so the p ≈ 2
manufactured-solution verification carries over. One agent-generated, parametrized solver
(normalized coords `x = R/R0`) serves all machines; per-machine coefficients come from a PETSc
options-file computed in Python.

```bash
# (a) agent-generate the shaped solver (mcp-test venv + Argo), same pipeline, new problem:
cd /home/sarthak.sharma/petsc_mcp_servers_tokamak
env PYTHONPATH=$MCP PETSC_DIR=$HOME/petsc PETSC_ARCH=arch-linux-c-opt \
    $PYV src/orchestrate_tokamak.py --problem shaped

# (b) verify convergence + q-profile + figures, per machine (/usr/bin/python3, NOT mcp-test):
env PETSC_DIR=$HOME/petsc PETSC_ARCH=arch-linux-c-opt \
    $PY3 src/verify_shaped.py --machines iter nstx xpoint --sizes 33 65 129 257

# (c) cross-check q + shape against the FreeGS reference in ~/tokamak (its own venv, spawned):
$PY3 src/crosscheck_freegs.py --machines iter nstx xpoint --run <run-id>

# (d) metrics (per-machine table) + combined poster figures:
$PY3 src/collect_metrics.py --run <run-id>
$PY3 src/make_shaped_figures.py --run <run-id>
```

Artifacts land under `artifacts/<run>/shaped/<machine>/` (`verification.json`, `<machine>.opts`,
`sidecar.json`, `flux_surfaces.png`, `qprofile.png`, `convergence.png`, `crosscheck.json`) plus
`artifacts/<run>/shaped_summary.json`; combined figures go to `figures/shaped_*.png`.

Notes / gotchas:
- The **Python analysis modules** (`cerfon_freidberg.py`, `verify_shaped.py`, `qprofile.py`,
  `crosscheck_freegs.py`, `make_shaped_figures.py`) need numpy/scipy/sympy → run them with
  **`/usr/bin/python3`**, never the mcp-test venv (which has no numpy).
- FreeGS runs in **`~/tokamak/.venv`** (numpy<2/scipy<1.14), spawned as a subprocess; it is never
  imported into this repo's interpreters.
- Multi-rank runs need **PETSc's own** `mpiexec` (`$PETSC_DIR/$PETSC_ARCH/bin/mpiexec`); the
  system `/usr/bin/mpiexec` uses an incompatible PMI and aborts `PetscInitialize`.
- `src/verify_tokamak.py` (the toy sin·sin verifier) refuses a shaped run — use `verify_shaped.py`.

## Troubleshooting

- *Inner agent says the only tool is "DesignSync" / cannot compile* → you are on an old
  `petsc_mcp_servers` without the `getScriptPort` absolute-path fix; check out branch
  `tokamak-improvements` or apply `patches/`.
- *`ModuleNotFoundError: pde_modeling_mcp_server`* → set `PYTHONPATH=$MCP`.
- *documentation/RAG server errors* → expected here (docs not built, no NVIDIA key); the
  code generator runs compile-run-only by design.
- *figures step: no numpy/matplotlib* → use `/usr/bin/python3`, not the mcp-test venv.
