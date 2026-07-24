# Built-in orchestrator demo — 2026-07-24 (as-shipped run)

This directory captures a **faithfulness demo** of the *shipped* LLM orchestrator
(`orchestrator_mcp_server.orchestrate_async`) driving the same four PETSc MCP servers our
project-owned driver uses. Unlike our `src/orchestrate_tokamak.py` driver — which sequences
the agents from Python and logs structured artifacts — here an **inner Claude agent** decides
the sequence itself, given only the instruction to use the four servers in order. This is the
proposal's top-of-hierarchy "orchestration agent" running end to end.

Prompt (verbatim spec): `the Grad-Shafranov equilibrium for a tokamak plasma`.

> **Read the fixed, fully-successful companion run first if you just want the result:**
> [`../orchestrator-20260724-fixed/`](../orchestrator-20260724-fixed/). This dir is the
> honest *as-shipped* run, which surfaced a real (and now fixed) bug in the upstream
> orchestrator.

## What happened (chronological, from `transcript.log`)

The inner agent drove all four servers **in the correct order, entirely on its own**:

1. **PDE modeling** (`mcp__PDE_modeling__generate_model`) → chose the **Grad–Shafranov
   equation with a Solov'ev *linear* source** on a rectangular (R,Z) cross-section,
   homogeneous Dirichlet BCs. Weak form `∫ (1/R)∇ψ·∇v = ∫ (C1 R + C2/R) v`.
2. **Numerical analysis** (`select_approach`, `petsc_solver`, `grid_and_discretization_to_petsc_dm`)
   → structured grid + finite elements → a linear elliptic solve. (It gracefully retried
   `petsc_solver` with the keyword `linear` after the tool first returned `Unknown`.)
3. **Code generation** (`mcp__Code_generator__generate_code`) → a complete **DMPLEX + PetscFE**
   solver (P1/P2 Lagrange, `SNES` with a single Newton step driving a `KSP` linear solve).
   The code-generator's own nested compile-run agent **compiled it cleanly and ran it to
   convergence**: `SNES CONVERGED_FNORM_RELATIVE` (1 Newton it), `KSP CONVERGED_RTOL`,
   **741 DOFs**, `||psi||_2 = 3.6217`, `||psi||_inf = 0.2226`, **"SOLVE CONVERGED
   SUCCESSFULLY"** (code-gen: 36 loops, 9 tool calls).
4. **PETSc compile and run** (`create_file_from_string` → `make`) → the orchestrator itself
   re-uploaded the solver and **re-compiled it cleanly** (`returncode 0`, no warnings), then
   issued its **first** `run_executable`…

…and at that exact message the run tripped the **hardcoded `cntlimit = 35`** in
`orchestrate_async` and returned:

```
FINAL_RESULT: {'failure_message': 'Too many iterations 36 of orchestration.'}
```

**So the pipeline substantively succeeded — a compiling, converged Grad–Shafranov solver —
but the shipped orchestrator declared failure.** The counter increments on *every* streamed
SDK message (assistant text + each tool-use + each tool-result), so a faithful four-stage
run with one tool retry simply runs past 35 before the final verification run can finish.

## The fix

This is the same failure mode already fixed one level down in the code generator (see
`docs/AGENT_SYSTEM_CHANGES.md` change #5). We applied the analogous change #6 to the
orchestrator — raise `cntlimit` 35→80 and instruct the agent to compile+run **once** (no
polynomial-degree / MPI-rank sweeps). Committed on branch `tokamak-improvements`
(`1fcfd95`), mirrored in `patches/0004-orchestrator-*.patch`. The re-run with that fix is
[`../orchestrator-20260724-fixed/`](../orchestrator-20260724-fixed/) and completes with
`I have completed the orchestration`.

## Files here

| File | What it is |
|---|---|
| `transcript.log` | Full run log: every inner-agent message, tool call, and tool result, plus the final result dict. The authoritative record. |
| `grad_shafranov.c` | The solver the agents wrote (copied from the compile-run work dir `$PETSC_DIR/$PETSC_ARCH/work`). DMPLEX + PetscFE. |
| `server_logs/*.stdout` | Per-sub-server stdio logs from this run: `pde_modeling`, `na`, `claude_code_generator`, and the `compile_run` instances (the code-gen server spawns its own compile-run; the orchestrator spawns another). |

## Reproduce

```bash
cd /home/sarthak.sharma/petsc_mcp_servers          # must be on branch tokamak-improvements
env PYTHONPATH=$PWD PETSC_MCP_SERVERS_STDIO=True \
  /home/sarthak.sharma/.venvs/mcp-test/bin/python -u -c \
  "import asyncio, orchestrator_mcp_server as o; \
   print(asyncio.run(o.orchestrate_async('the Grad-Shafranov equilibrium for a tokamak plasma')))"
```

Wall-clock this run: **~9m15s** (2026-07-24T21:33:58Z → 21:43:13Z). Expect variation; the
run nests deeply (orchestrator → inner Claude → 4 stdio sub-servers, and the code generator
spawns yet another Claude).
