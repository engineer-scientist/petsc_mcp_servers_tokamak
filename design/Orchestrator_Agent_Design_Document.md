# Orchestrator Agent

> **Proposal layer:** Workflow Control (McInnes et al., DE-FOA-0003612, Fig. 2 —
> *Orchestrator Agent*; "maintains state, assigns tasks, and routes outputs with diagnostic
> context," supported by Shared Memory and Persistent Decision-Aware Memory).
> **Concrete realization:** two coexisting implementations —
> 1. **Built-in LLM orchestrator** `orchestrator_mcp_server.py` (port **8086**): an inner
>    Claude that autonomously drives the four sub-servers (PDE modeling → NA → code generator →
>    compile/run) under `bypassPermissions`. Tool: `orchestrate(specification)`.
> 2. **Project-owned deterministic driver** `src/orchestrate_tokamak.py` (this repo): calls the
>    same specialist agents in sequence but with **explicit control flow, artifact capture, and
>    verification hooks**.
> **In this project:** the driver produced the canonical verified run; the built-in orchestrator
> was demonstrated end-to-end in `artifacts/orchestrator-20260724-fixed/`. See
> `docs/ARCHITECTURE.md`, `docs/SESSION_LOG.md`, `docs/AGENT_SYSTEM_CHANGES.md` (#6).

## External Design

**Purpose and Goal**

Owns the **end-to-end workflow**: turn a plain-language problem into a verified, runnable
simulation by sequencing the specialist agents, carrying state and artifacts between them, and
— per the proposal — **routing diagnostics on failure and deciding rollback/replan**. It is the
only component that sees the whole problem-to-solution loop and the "control moves freely as the
solution is iteratively refined."

**Scope**

* **Task sequencing** — invoke Mathematical Modeling → Numerical Analysis → HPC Code Generation → Compile & Run (→ Visualization & Analysis, once that agent exists) in the right order.
* **State & artifact routing** — pass each agent's structured output to the next; retain all intermediates (the "accumulated structured artifacts").
* **Verification-driven control** — treat verification/diagnostic signals as first-class: on incompatibility, non-convergence, or nonphysical output, **rollback** to the appropriate upstream agent with enriched diagnostics rather than pushing forward.
* **Provenance & reproducibility** — (driver) record inputs, transcripts, decisions, and a per-run dataflow map so any run can be reproduced/audited.
* **Resumability** — (driver) be restartable and logged so multi-session work continues cleanly.

**Owned concepts:** the workflow, the run's control state, the rollback policy, and (with the
Persistent Memory agent) the run record.

**Out of Scope**

* Does **no modeling, numerical analysis, or code generation itself** — it must always delegate to the specialist agents (the built-in prompt says so explicitly).
* Does not compile/run directly beyond delegating to the Compile & Run agent (built-in: it calls the compile-run server; it is told not to use Bash/Write).
* Does not own the scientific correctness verdict — that is the Visualization & Analysis agent's; the Orchestrator *acts on* it.

**Inputs**

* A single `specification` string (the plain-language problem), e.g. *"the Grad–Shafranov equilibrium for a tokamak plasma."*
* Access (as sub-servers / clients) to the specialist agents and the Compile & Run agent.
* (Driver) configuration: run-id, output dir, which agents to invoke, verification settings.

**Outputs**

* **Built-in:** a completion signal — it watches for the inner agent's message *"I have completed the orchestration"* and returns `{}` on success, or `{'failure_message': ...}` (e.g., "Too many iterations …", or a model/gateway error).
* **Driver:** a fully populated `artifacts/<run-id>/` directory — per-stage inputs, transcripts, structured outputs (`model.*`, `na.*`, `code`/`output`), a `DATAFLOW.md` lineage map, `metrics.md`, and a `LATEST` pointer — plus the exit status of each stage (`ok`/failed).

**Interaction Patterns**

* **Built-in** (`orchestrator_mcp_server.py`): opens one inner Claude with **four MCP sub-servers** attached (`pde_modeling`, `na`, `claude_code_generator`, `compile_run`), `allowed_tools=["mcp__*"]`, `permission_mode="bypassPermissions"`; instructs it to use each server in order and to **compile+run exactly once** (no rank/degree/grid sweeps). Deep nesting results (orchestrator → inner Claude → 4 servers, and the code generator spawns yet another Claude).
* **Driver** (`src/orchestrate_tokamak.py`): calls each specialist agent's async function directly, in Python, capturing every artifact and inserting verification/rollback hooks as explicit steps — controllable and provenance-rich, while exercising the *same* agents, tools, and LLM backend.
* Both are the top of the hierarchy; they call down, specialists do not call up (specialists return to the Orchestrator, which routes onward — see the NA agent's resolved interaction question).

## Internal Design

**Skills List**

* **Ordered fan-out** — the fixed pipeline order and the rule that modeling/NA/codegen are always delegated, never done inline.
* **Run-once discipline** — compile and run the generated program a single time; do not sweep MPI ranks, polynomial degrees, or grid sizes (a budget/robustness rule from `docs/AGENT_SYSTEM_CHANGES.md` #6).
* **Completion detection** — recognize the exact sentinel *"I have completed the orchestration"* (built-in) or all-stages-`ok` (driver).
* **Rollback/replan policy** *(design intent, realized incrementally in the driver)* — map a downstream diagnostic to the upstream agent to re-invoke, with the diagnostic attached.
* **Artifact capture & lineage** (driver) — write per-stage input/transcript/output and a `DATAFLOW.md`; maintain `LATEST`.
* **Resumable staging** (driver) — skip already-completed stages on restart using the artifact store.

**Tool List**

* **Built-in:** exposes `orchestrate(specification)`; inner agent granted the four sub-servers above; denied Bash/Write. Underlying model: Claude Opus 4.8 via `claude_agent_sdk` → ANL Argo.
* **Driver:** the Python MCP clients / async entry points of the specialist agents, plus `src/verify_tokamak.py` and `src/collect_metrics.py`; filesystem access for the `artifacts/` store (the driver, unlike the built-in agent, *is* allowed to write, because it is project-owned infrastructure, not an LLM).
* (Both, design intent) the **Persistent Decision-Aware Memory** agent as the backing store and the **Shared Memory** (tools/compilers/models).

**Validation Techniques**

* **Sub-server availability check** — verify the expected agents are reachable before starting (built-in tells the inner agent to exit if it can't see four servers; the driver checks its clients).
* **Loop-budget guard** — abort with a `failure_message` if streamed-message count exceeds `cntlimit = 80` (raised from 35 so faithful multi-stage runs finish before the cap — the #6 fix).
* **Per-stage success gating** (driver) — do not advance until the current stage returns a valid structured artifact; a failing stage triggers rollback rather than silent continuation.
* **Independent end verification** (driver) — after code gen, run the convergence/conservation study before declaring the run successful (the built-in agent stops at "compiled and ran once").
* **Model/gateway error detection** — surface "There's an issue with the selected model" immediately.

**Required Logging**

* **Built-in:** every inner assistant message, each `ToolUseBlock` (which sub-server tool + input), each tool result, and the final completion/failure — the full orchestration transcript (captured to the sub-server stdio logs and, in demos, to `artifacts/orchestrator-<date>/`).
* **Driver:** per-stage `*_input.txt`, `*_transcript.log`, structured outputs, `DATAFLOW.md`, `metrics.md`, and a run `README.md`; `artifacts/README.md` documents the schema.

## Additional Information

* **Why two orchestrators.** The built-in LLM orchestrator demonstrates the proposal's
  "autonomous end-to-end" thesis; the project driver adds what a demo can't: guaranteed
  artifact capture, real verification, rollback hooks, and resumability — "faithful to the
  architecture (same agents, tools, LLM) while being robust, controllable, and provenance-rich"
  (`docs/ARCHITECTURE.md`).
* **The counter subtlety.** `cntlimit` counts *every* streamed SDK message — assistant text,
  each tool-use, and each tool-result. A faithful four-stage run plus one retry exceeded the
  old cap of 35 *exactly as it issued its first run*, mislabeling a converged solve as "Too
  many iterations." This project's #6 fix (cap → 80, run-once) resolved it; see
  `artifacts/orchestrator-20260724/` (failure) vs `…-fixed/` (success).
* **Persistent memory is the missing half.** Fig. 2 pairs the Orchestrator with a Persistent
  Decision-Aware Memory; this project realizes that as the `artifacts/` store today and
  proposes formalizing it (see the Persistent Memory agent design doc).

## Failure Modes

* **Loop-budget exhaustion** — long faithful runs mislabeled as failures (fixed by #6; still a risk if a stage retries excessively).
* **Missing/unreachable sub-server** — the pipeline can't proceed; the inner agent should exit, but historically a mis-resolved server path caused a silent fallback to a remote URL and un-runnable code (root cause fixed upstream, #2).
* **Doing work inline** — an LLM orchestrator that "helpfully" writes code itself instead of delegating, violating the hierarchy and losing provenance. Mitigation: explicit prompt prohibition; deny Bash/Write.
* **No rollback on a bad result** — pushing forward after a nonphysical/non-convergent result because the built-in agent stops at "ran once." Mitigation: the driver's post-run verification gate; promoting the Visualization & Analysis agent so signals are actionable.
* **Deep-nesting fragility** — orchestrator → Claude → code generator → Claude → compile-run is slow and can time out or need a retry (`docs/USAGE.md`).
* **State loss across sessions** — without the persistent store, a crash loses intermediate artifacts. Mitigation: the driver persists every stage and is resumable.
