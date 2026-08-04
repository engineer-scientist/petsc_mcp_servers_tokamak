# HPC Code Generation (and Execution) Agent

> **Proposal layer:** Agent Execution (McInnes et al., DE-FOA-0003612, Fig. 2 —
> *HPC Code Generation Specialist Agent*).
> **Concrete realization:** `petsc_claude_code_generator_mcp_server.py` (port **8083**). An
> **LLM agent that drives other agents**: it opens an inner Claude (`claude_agent_sdk` → ANL
> Argo, Opus 4.8) under `permission_mode="bypassPermissions"` and gives it the **Compile & Run**
> agent as an MCP sub-server (plus **Documentation** and **RAG** *only if available on the host*).
> Tool: `generate_code(specification)`.
> **In this project:** from the Grad–Shafranov numerical plan it produced a **267-line PETSc
> `DMDA` + `SNES` solver** (true Jacobian, ghosted residual, manufactured-solution check) that
> **compiled and ran on 1 and 4 MPI ranks with no human edits** (canonical run
> `artifacts/run-20260723-113024/`). See `docs/ARCHITECTURE.md`, `docs/AGENT_SYSTEM_CHANGES.md`.

## External Design

**Purpose and Goal**

Transforms the validated modeling and numerical decisions into a **scalable, portable PETSc
implementation** and proves it at least *runs* before returning it. The proposal frames it as
"API and abstraction selection → code synthesis → scalability-aware generation → execution and
quality checks," with **embedded verification** (manufactured solutions, convergence,
consistency) and performance telemetry. It is the boundary where reasoning becomes an artifact
that a compiler and MPI accept.

**Scope**

* **API/abstraction selection** — choose the concrete PETSc objects that realize the NA plan (`DMDA`/`DMPLEX`/`DMSTAG`/`DMSWARM`, `SNES`/`KSP`/`TS`, `PetscFE`, etc.).
* **Code synthesis** — emit concise, idiomatic C (Phase II: C++/Python) that conforms to library conventions: **modern PETSc style** (`PetscCall(...)` wrapping, **not** the old `ierr =` idiom), no `%D` printf formats.
* **Scalability-aware generation** — correct parallel decomposition (ghosted residual/Jacobian, MPI-safe I/O and error reduction) so the same code runs on 1 or many ranks.
* **Execution & quality checks** — *use the Compile & Run agent* to actually compile and run the program; detect and repair compile/link/runtime errors in a loop until it succeeds once.
* **Embedded verification** — include the verification the NA agent prescribed (e.g., a manufactured/known-solution error check) directly in the generated program.
* **Independent re-verification** — after the inner agent reports success, the server itself re-creates the file and re-runs `make` through a fresh Compile & Run client, because "LLMs are not trustworthy" (comment in the source).

**Owned concepts:** the source code artifact, its build, and the first successful run. It is
the single authority on "here is code that compiles and runs."

**Out of Scope**

* Does not choose the model (Mathematical Modeling) or the discretization/solver plan (Numerical Analysis) — it *realizes* them.
* Does not itself provide the shell/compiler; it delegates every filesystem/compile/run action to the **Compile & Run** agent (it is explicitly told **not** to use the Bash or Write tools).
* Does not do publication-quality post-processing/plots or scientific diagnosis (Visualization & Analysis).
* Does not do exhaustive performance sweeps: it is instructed to **stop after the first successful compile+run** (no extra MPI-rank counts, grid sizes, or polynomial degrees).

**Inputs**

* A `specification` string — in practice the model + numerical plan assembled by the Orchestrator/driver (equation, BCs, `DMType`, solver class, verification approach).
* Ambient PETSc environment (`PETSC_DIR`, `PETSC_ARCH`) via the Compile & Run agent.

**Outputs**

A dictionary:

| Key | Meaning |
|---|---|
| `code` | the generated PETSc C source |
| `output` | stdout/stderr of the first successful run |
| `response_loops` | number of `receive_response()` iterations consumed |
| `tool_cnt` | number of sub-server tool calls made |
| `failure_message` | present iff generation/compile failed (e.g., "Too many iterations …", model/credit errors, or a real compile error captured on the independent recompile) |

The `code` + `output` are archived by the Persistent Memory agent and (in this project) fed to
`src/verify_tokamak.py` for the convergence study and to the Visualization & Analysis workflow.

**Interaction Patterns**

* Invoked by the Orchestrator/driver **after** Modeling and Numerical Analysis.
* **Acts as a client of the Compile & Run agent** (always) and of the Documentation/RAG agents (when available) — a higher-level agent delegating to lower-level ones, the proposal's "agents = remotely-callable objects."
* Runs an internal **generate → compile → read errors → fix** loop, capped at `cntlimit = 80` streamed messages; returns the moment the program compiles and runs once.
* On failure, returns a `failure_message`; the Orchestrator decides whether to rollback to the NA or Modeling agent with the diagnostics.
* Spawns exactly one inner Claude per call; that inner agent may fan out to the sub-servers.

## Internal Design

**Skills List**

* **Sub-server provisioning** — attach only sub-servers that can actually run on this host: Compile & Run is required; Documentation is added only if `petscmcp.documentationAvailable()`; RAG only if `petscmcp.ragAvailable()`. Tell the inner agent the true count and to **exit immediately if it lacks the compile-run server** (this project's graceful-degradation fix — see `docs/AGENT_SYSTEM_CHANGES.md` #4).
* **Modern-PETSc coding standard** — always `PetscCall(...)`; never `ierr =`; never `%D` in `printf`-family calls; idiomatic DM/SNES/KSP/TS usage.
* **Compile-fix loop** — read compiler/linker stderr from the Compile & Run agent and repair the source; repeat within the loop budget.
* **First-success stop** — as soon as it compiles and runs once, emit the final `{code, output}` JSON in a `TextBlock` and stop (no rank/grid/degree sweeps). This is the loop-budget fix (#5) that prevented correct solvers from being mislabeled failures.
* **Structured-return discipline** — the final answer must be a JSON dict with keys `code` and `output` inside a triple-backtick ` ```json ` fence; if omitted, the server re-prompts ("You did not return the code and its output as JSON …").
* **Independent verification** — never trust the inner agent's "it worked"; recompile the returned code through a fresh Compile & Run client and downgrade to `failure_message` if it does not build.

**Tool List**

* Exposes `generate_code(specification)` (MCP tool).
* Inner agent is granted, via `mcp_servers`: **PETSc compile-run** (always) and optionally **PETSc documentation**, **PETSc RAG**; `allowed_tools=["mcp__PETSc*"]`; `permission_mode="bypassPermissions"`. It is **denied** Bash/Write.
* The server itself uses `petsc_compile_run_mcp_client.PetscCompileRunMCPClient` for the independent recompile.
* Underlying model: Claude Opus 4.8 via `claude_agent_sdk` → ANL Argo (`petscmcp.defaultModel`).

**Validation Techniques**

* **Loop-budget guard** — abort with a `failure_message` if `cnt > cntlimit (80)` (prevents runaway; the cap was raised from 30 precisely so *correct* programs finish before it trips).
* **Independent recompile** — the server's own `create_file_from_string('mytest.c', code)` + `make('mytest')`; any `MCPDynamicClientReturnCode` becomes a `failure_message` carrying the real stderr.
* **Model/credit error detection** — scans assistant text for "There's an issue with the selected model" / "Credit balance is too low" and fails fast with that message.
* **Embedded scientific check** — the generated program itself computes the manufactured/known-solution error, so a "successful run" also reports a correctness number (later confirmed by the convergence study).
* **Style conformance** — the coding-standard skill is a validation target (PetscCall/no-%D) reducing subtle portability bugs.

**Required Logging**

* Which sub-servers were attached ("Code generator using sub-servers: …").
* Every inner assistant message, every `ToolUseBlock` (tool name + input), and every tool result (stdout/stderr) — the full code-gen ⇄ compile-run transcript.
* The extracted JSON block, `response_loops`, `tool_cnt`, and any `failure_message`.
* In this project the driver saves `codegen_input.txt`, the complete `codegen_transcript.log` (including inter-agent tool calls), and the final `code`/`output` under `artifacts/<run-id>/`; `metrics.md` records loops, tool calls, and wall-clock.

## Additional Information

* **This agent is itself an orchestrator-in-miniature.** It runs a full inner agentic loop (Claude ↔ Compile & Run), which is why the loop budget and "stop after first success" prompt matter so much: the counter increments on *every* streamed message (assistant text, each tool-use, each tool-result). The upstream fixes here (#4, #5 in `docs/AGENT_SYSTEM_CHANGES.md`) are the ones this project contributed.
* **Nesting depth.** Under the built-in Orchestrator this is Claude → (orchestrator) → Claude → (this agent) → Claude → Compile & Run — deep nesting that is slow and occasionally needs a retry (see `docs/USAGE.md`).
* **"Do not trust the LLM."** The independent recompile is a deliberate defense: the returned `code` is proven to build by the *server*, not merely asserted by the model.

## Failure Modes

* **Missing compile-run server** — if the essential sub-server can't start (e.g., wrong CWD before the `getScriptPort` fix), the inner agent has no way to compile and should exit; historically it silently fell back to a remote URL and produced un-runnable code (root cause fixed upstream, #2).
* **Loop-budget exhaustion** — a thorough agent that also sweeps ranks/grids runs out of messages before emitting its JSON, so a *working* program is reported as "Too many iterations" (fixed by #5: cap 80 + first-success stop).
* **Non-conforming final message** — inner agent returns prose instead of the `code`/`output` JSON; mitigated by the re-prompt, but repeated failure wastes budget.
* **Style/portability bugs** — `ierr =`, `%D`, or non-ghosted parallel code that builds on 1 rank but fails on many; mitigated by the coding standard and (optionally) multi-rank runs, though the first-success stop means multi-rank isn't guaranteed to be exercised every run.
* **Compiles but wrong** — code that runs yet is physically incorrect; caught only by the embedded verification + the downstream convergence/conservation analysis, not by "it ran."
* **Model/gateway errors** — Argo model unavailable or credit issues; detected and returned as `failure_message`.
* **Shared work directory clobbering** — all callers share `$PETSC_DIR/$PETSC_ARCH/work`; concurrent runs can overwrite files (use unique filenames; see `docs/ENVIRONMENT.md` gotcha #5).
