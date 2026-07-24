# Built-in orchestrator demo — 2026-07-24 (fixed run, full success)

The **shipped LLM orchestrator** (`orchestrator_mcp_server.orchestrate_async`) driving all
four PETSc MCP servers end to end on the tokamak problem, with the upstream iteration-cap bug
fixed (`docs/AGENT_SYSTEM_CHANGES.md` change #6; branch `tokamak-improvements` commit
`1fcfd95`; `patches/0004-orchestrator-*.patch`). This is the clean companion to the honest
as-shipped run in [`../orchestrator-20260724/`](../orchestrator-20260724/), which surfaced the
bug (it hit the hardcoded `cntlimit = 35` mid-verification and reported a false failure).

Prompt (verbatim spec): `the Grad-Shafranov equilibrium for a tokamak plasma`.

## Result

The inner agent drove the four servers **in order, on its own**, and finished cleanly:

1. **PDE modeling** → Grad–Shafranov, steady & linear, Solov'ev source; weak form
   `∫ (1/R)∇ψ·∇v = ∫ (C1 R + C2/R) v`, homogeneous Dirichlet BC on `[0.5,1.5]×[−1,1]`.
2. **Numerical analysis** → structured grid + finite elements → linear elliptic solve
   (again gracefully retried `petsc_solver` with `linear` after an `Unknown`).
3. **Code generation** → **DMPLEX + PetscFE**, degree-1 Lagrange, 16×16 box mesh, `SNES`
   (linear, via `DMPlexSetSNESLocalFEM`) → `KSP`. Self-tested by the code-gen agent:
   `||psi||_2 = 2.04156`, **225 DOFs**, `rc=0` (46 loops, 12 tool calls).
4. **PETSc compile and run** → the orchestrator saved the file, `make` succeeded
   (`returncode 0`, no warnings), and it ran the program **exactly once**:
   `Grad-Shafranov solve complete, ||psi||_2 = 2.04156`, `Number of degrees of freedom = 225`,
   `rc=0`.

Final messages:

```
I have completed the orchestration
FINAL_RESULT: {}
```

`{}` is the **success** return of `orchestrate_async` (an empty `results` dict; no
`failure_message`). Wall-clock: **~12m44s** (2026-07-24T21:49:12Z → 22:01:56Z).

Note the physics is genuinely independent of our project driver's canonical run
(`run-20260723-113024/`), which used a **finite-difference `DMDA`** solver and a manufactured
sine-bump solution; here the agent independently chose an **unstructured `DMPLEX` + `PetscFE`
finite-element** discretization of the same Grad–Shafranov (Solov'ev) equilibrium.

## Files here

| File | What it is |
|---|---|
| `transcript.log` | Full run log: every inner-agent message, tool call, tool result, and the final `{}`. Authoritative record. |
| `grad_shafranov.c` | The solver the agents wrote (DMPLEX + PetscFE), from `$PETSC_DIR/$PETSC_ARCH/work`. |
| `server_logs/*.stdout` | Per-sub-server stdio logs from this run (`pde_modeling`, `na`, `claude_code_generator`, and the `compile_run` instances). |

## Reproduce

```bash
cd /home/sarthak.sharma/petsc_mcp_servers          # branch tokamak-improvements (has the fix)
env PYTHONPATH=$PWD PETSC_MCP_SERVERS_STDIO=True \
  /home/sarthak.sharma/.venvs/mcp-test/bin/python -u -c \
  "import asyncio, orchestrator_mcp_server as o; \
   print(asyncio.run(o.orchestrate_async('the Grad-Shafranov equilibrium for a tokamak plasma')))"
```
