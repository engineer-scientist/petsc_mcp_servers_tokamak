# Accumulated artifact store

This directory is the project's **accumulated structured-artifact store** — the
"collections of structured artifacts from previous runs of the framework" described in the
DOE proposal. Every run of `src/orchestrate_tokamak.py` writes one self-contained,
timestamped subdirectory `run-YYYYmmdd-HHMMSS/` capturing **all important inputs and
outputs of every AI agent**, including the data passed between agents. Nothing is a black
box: for each run you can read exactly what each agent received, what it produced, and how
the pieces were handed off.

`LATEST` names the most recent run. The **canonical Session-1 run is
`run-20260723-113024/`**.

## What every file in a `run-*/` directory is

| File | Produced by | What it is |
|---|---|---|
| `manifest.json` | driver | **Provenance**: run id, host, model, `ANTHROPIC_BASE_URL`, git SHAs of both repos, per-stage status/timing, and the verbatim human input specs. |
| `DATAFLOW.md` | driver | **Human-readable lineage**: the agent-to-agent hand-offs with the actual values and pointers to every file below. Start here. |
| `model_input.txt` | driver→Modeling agent | Exact problem statement sent to the **Mathematical Modeling** agent. |
| `model_transcript.log` | Modeling agent | Full raw LLM response (the whole conversation). |
| `model.json` | Modeling agent | Structured result: PDE `name`, `time-dependent`, request. |
| `model.tex`, `model.html`, `model_ufl.py`, `model_full.md` | Modeling agent | The PDE in LaTeX, MathJax HTML, FEniCS UFL, and the full markdown answer. |
| `na_input.txt` | driver→Numerical Analysis agent | Exact input to the **Numerical Analysis** agent (science spec + model facts). |
| `na_transcript.log` | Numerical Analysis agent | Full raw LLM response (grid/discretization/solver reasoning). |
| `na.json` | Numerical Analysis agent | Structured decision: `grid`, `discretization`, PETSc `DM`, `solver`. |
| `codegen_input.txt` | driver→Code-Gen agent | Exact engineering spec sent to the **HPC Code Generation** agent. |
| `codegen_transcript.log` | Code-Gen ⇄ compile-run agents | **The inter-agent conversation**: every `create_file_from_string`, `make`, `run_executable` call the code-gen agent made to the **compile-run** agent, and each result. |
| `grad_shafranov.c` | Code-Gen agent | **The HPC code the agents wrote** (the PETSc `DMDA`+`SNES` Grad–Shafranov solver). |
| `codegen_output.txt` | compile-run agent | Stdout of the generated program actually running on the machine. |
| `codegen.json` | Code-Gen agent | Metadata: LLM response loops, tool-call count. |
| `full_pipeline_transcript.log` | driver | The entire driver run log (all stages concatenated), authoritative record. |
| `verification.json` | `verify_tokamak.py` | Independent verification: grid ladder, errors, observed order of accuracy. |
| `gs_convergence.png`, `gs_flux_surfaces.png` | `verify_tokamak.py` | Figures from the verified solution. |
| `metrics.json`, `metrics.md` | `collect_metrics.py` | Decision-gate metrics (correctness / efficiency / human effort). |

## Where the agents actually ran the code

The compile-run agent creates, compiles, and runs programs in its work directory
`$PETSC_DIR/$PETSC_ARCH/work` (here `~/petsc/arch-linux-c-opt/work/`), which holds the live
`.c` sources and compiled binaries (`gradshafranov`, `gs_mms`, …). The authoritative,
version-controlled copy of the generated solver is `grad_shafranov.c` in each run dir.

## Reading a run

1. Open `DATAFLOW.md` — the map of the whole run.
2. Follow the hand-offs: `model_input.txt` → `model.json`; `na_input.txt` → `na.json`;
   `codegen_input.txt` → `codegen_transcript.log` → `grad_shafranov.c` + `codegen_output.txt`.
3. Cross-check the physics in `verification.json` and the figures.

## `orchestrator-*/` — built-in LLM orchestrator demos

The `run-*/` dirs above come from our project-owned driver (`src/orchestrate_tokamak.py`),
which sequences the agents from Python. The `orchestrator-*/` dirs are a different thing: the
**shipped** `orchestrator_mcp_server` LLM agent driving the same four servers, where an inner
Claude decides the sequence itself. Each has its own `README.md`, `transcript.log` (the
authoritative record), the generated `grad_shafranov.c`, and `server_logs/` (per-sub-server
stdio logs).

- **`orchestrator-20260724/`** — honest *as-shipped* run. Drove all four servers correctly and
  produced a compiling, converged DMPLEX+PetscFE solver, but tripped the upstream
  `cntlimit = 35` during its final verification run and returned a (false) `failure_message`.
- **`orchestrator-20260724-fixed/`** — same run after the analogous cap fix
  (`docs/AGENT_SYSTEM_CHANGES.md` #6, `patches/0004`): completes cleanly with
  `I have completed the orchestration` and `FINAL_RESULT: {}` (success).
