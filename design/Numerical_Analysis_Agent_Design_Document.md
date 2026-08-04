# Numerical Analysis (NA) Agent

> **Proposal layer:** Agent Execution (McInnes et al., DE-FOA-0003612, Fig. 2 —
> *Numerical Analysis Specialist Agent*).
> **Concrete realization:** `na_mcp_server.py` (port **8085**). A **hybrid** agent: one
> LLM-reasoning tool (`select_approach`, run under `petscmcp.forbidTools`) plus two
> **deterministic, rule-based** tools (`grid_and_discretization_to_petsc_dm`, `petsc_solver`)
> that encode PETSc's own compatibility rules. ARCHITECTURE.md labels it "yes + rules."
> **In this project:** on the Grad–Shafranov spec it returns `{grid: unstructured-grid,
> discretization: finite-element}` → `DMPLEX`; nonlinear → `SNES` (and the driver's canonical
> run used the structured `DMDA` + `SNES` path). See `docs/ARCHITECTURE.md`.

## External Design

**Purpose and Goal**
*Selects appropriate griding, discretization, and solver techniques for a given PDE model. May also determine specific techniques for confirming that the resulting codes perform as expected, for example, using the method of manufactured solutions and convergence studies.*

The NA agent maps a well-posed formulation to a **discretization + solver plan** that PETSc
can actually realize. The proposal frames this as a **knowledge-guided, constraint-driven
decision problem**: choices are informed by mathematical structure (stiffness, coupling,
conservation) and constrained by PETSc's compatibility rules, not by free-form guessing.

**Scope**
*This is the "what" of the agent's work.*

* **Discretization selection** — pick the grid (structured / staggered-structured / particle / unstructured) and the spatial discretization (finite differences / finite element / discontinuous Galerkin) from problem class, geometry, and regularity.
* **Solver identification** — from the PDE's character (linear / nonlinear / time-dependent) choose the PETSc solver class: `KSP` (linear), `SNES` (nonlinear), or `TS` (time-dependent).
* **PETSc realization mapping** — translate `(grid, discretization)` into the concrete PETSc `DMType` via fixed rules: `structured-grid + finite-differences → DMDA`; `staggered-structured-grid + finite-differences → DMSTAG`; `particle → DMSWARM`; anything else (unstructured / FE / DG) `→ DMPLEX` (with an explicit error that **unstructured + finite-differences is unsupported**).
* **Configuration generation** — (design intent) preconditioner/KSP/SNES/TS options informed by PETSc conventions.
* **Performance-aware adaptation** — (design intent) parallel decomposition and GPU suitability.
* **Verification strategy** — prescribe *how* the generated code will be checked: **method of manufactured solutions (MMS)**, convergence/order-of-accuracy studies, and conservation checks. (This project realizes MMS with the Solov'ev exact solution — observed order **p = 2.00**; see `docs/VERIFICATION.md`.)

**Owned concepts:** grid, discretization, solver class, `DMType`, and the verification plan.
The NA agent is the single authority on "how do we discretize and solve this?"

**Out of Scope**

* Does not select or decide on the PDE model (that is the **Mathematical Modeling** agent).
* Does not directly produce code (that is the **HPC Code Generation** agent).
* Does not compile, run, or *execute* the verification it prescribes (that is Code Gen + Compile & Run + Visualization & Analysis); it specifies the plan.

**Inputs**

* Geometry, PDE model, and boundary/initial conditions — i.e., the Mathematical Modeling agent's output.
* Critically, the model's `time-dependent` flag and its (non)linearity, which drive the solver-class rules.

The prompt to `select_approach` should carry the mathematical structure and problem class.
It should **not** dictate the grid/solver (that is what this agent decides). The two
rule-based tools take small, explicit string arguments (`grid`, `discretization`; or the
problem character) rather than free text.

**Outputs**

* **Gridding approach** (`grid`).
* **Spatial discretization approach** (`discretization`).
* **Time integration approach** (`integrator`) — only if the model is time-dependent.
* **PETSc `DMType`** (from `grid_and_discretization_to_petsc_dm`).
* **PETSc solver class** `TS`/`SNES`/`KSP` (from `petsc_solver`).
* **Verification approaches** (MMS, convergence study, conservation checks) with rationale.

`select_approach` returns a JSON dictionary `{grid, discretization[, integrator]}`; the two
rule tools return single strings. Together these are the "numerical plan" artifact archived
by the Persistent Memory agent and consumed by the HPC Code Generation agent.

**Interaction Patterns**

*Open question from the original template — "Should this agent pass the information back to
the orchestrator or should it use the code generation agent to construct the needed code? Or
both?"* **Resolution adopted in this project:** the NA agent **returns its plan to the caller
(Orchestrator or driver)**, which then invokes the Code Generation agent. This keeps the NA
agent stateless and single-responsibility, keeps the Orchestrator the sole owner of control
flow and rollback, and matches the proposal's hierarchy (Fig. 2) in which the Workflow Control
layer — not a peer specialist — routes work between execution agents. The built-in
`orchestrator_mcp_server.py` does exactly this: model → **NA** → code generator → compile/run.

* Invoked by the Orchestrator/driver **after** the Mathematical Modeling agent.
* May be **re-invoked on rollback** when downstream results are incompatible or unstable (e.g., the solver stalls, or convergence order is wrong) — the proposal's "incompatible or unstable decisions trigger rollback with enriched diagnostics."
* Does not spawn sub-agents. In Phase I `select_approach` reasons with retrieval-augmented PETSc knowledge (via the RAG/Documentation agents where available); the two rule tools are pure functions.

## Internal Design

**Skills List**

* **Discretization decision** — a fixed procedure mapping (problem class, geometry, regularity, conservation needs) → (grid, discretization); e.g., complex/shaped geometry ⇒ unstructured/FE; simple box + smooth solution ⇒ structured/FD.
* **Solver-class decision** — deterministic: time-dependent ⇒ `TS`; else nonlinear ⇒ `SNES`; else linear ⇒ `KSP`. (Encoded in `petsc_solver`; the LLM must not override it.)
* **DMType mapping** — the fixed compatibility table above, including the hard constraint that unstructured + finite-differences is rejected rather than silently "fixed."
* **JSON-only emission** — `select_approach` must return exactly one JSON object with keys `grid`, `discretization`, and optionally `integrator`; no prose, no tool use.
* **Verification-plan authoring** — choose MMS vs known-solution vs conservation checks appropriate to the model; specify the refinement sequence and the expected order of accuracy.
* **Configuration/PC selection** *(design intent / Phase II)* — pick KSP+PC (e.g., GMRES + AMG), SNES line search, TS scheme, using PETSc-derived compatibility rules and telemetry.

**Tool List**

* `select_approach(specification)` — **LLM tool**, runs under `petscmcp.forbidTools` (reason-only, no filesystem/shell); returns `{grid, discretization[, integrator]}`.
* `grid_and_discretization_to_petsc_dm(grid, discretization)` — **pure rule function**, returns a `DMType` string; raises on the unsupported unstructured+FD combination.
* `petsc_solver(problem)` — **pure rule function**, returns `TS`/`KSP`/`SNES`.
* Underlying model for the LLM tool: Claude Opus 4.8 via `claude_agent_sdk` → ANL Argo.
* *(Design intent)* read-only access to the **Documentation** and **RAG** knowledge agents for retrieval-augmented method selection.

**Validation Techniques**

* **Schema check** — `select_approach` output must be valid JSON with allowed enum values for `grid` and `discretization`; the server rejects non-JSON (`'LLM did not return correct JSON'`).
* **Compatibility check** — the DMType rule refuses illegal (grid, discretization) pairs, catching an inconsistent LLM choice before it reaches the coder.
* **Model-consistency check** — the solver class must agree with the model's time-dependence/linearity flags from the Modeling agent; `integrator` present **iff** the model is time-dependent.
* **No-tool invariant** — any tool call by the LLM aborts with `{'failure': 'LLM tried to use tool!'}`.
* **Verification-plan sanity** — the prescribed MMS/convergence study must be one the chosen discretization can actually exhibit (e.g., central FD ⇒ expected order 2), so a wrong observed order is a real signal, not a spec mismatch.

**Required Logging**

* The `specification` received and the raw LLM text before JSON extraction.
* The chosen `{grid, discretization, integrator}`, the resolved `DMType`, and the solver class.
* Any compatibility-rule rejection (with the offending pair) and any JSON-parse failure.
* In this project the driver persists `na_input.txt`, `na_transcript.log`, and the structured decision to `artifacts/<run-id>/`, and records the NA→codegen lineage in `DATAFLOW.md`.

## Additional Information

* **Why the rule tools are not LLM calls.** DMType and solver-class selection are exact,
  well-defined PETSc facts; encoding them as deterministic functions removes a whole class of
  hallucination and makes the plan reproducible. The LLM is used only where genuine judgment
  is needed (grid/discretization/integrator selection).
* **Verification is prescribed here, executed elsewhere.** The NA agent says "run MMS with a
  Solov'ev exact solution and expect 2nd-order convergence"; the coder embeds the check, the
  Compile & Run agent runs it, and the Visualization & Analysis agent measures the order. In
  this project that pipeline produced **p = 2.00, 2.00, 2.00** (`docs/VERIFICATION.md`).
* **Phase II.** Learned relationships from simulation telemetry (solver performance vs problem
  characteristics) will inform configuration and performance-aware adaptation; Phase I uses
  retrieval-augmented reasoning over curated PETSc expertise and benchmarks.

## Failure Modes

* **Non-JSON / malformed output** from `select_approach` — breaks the handoff. Mitigation: strict JSON-only emission skill + server-side parse guard.
* **Incompatible plan** — e.g., unstructured + finite-differences, or an enum value outside the allowed set. Mitigation: the DMType rule raises rather than guesses; schema validation on enums.
* **Solver/time-dependence mismatch** — choosing `KSP` for a nonlinear problem, or omitting `integrator` for a time-dependent one. Mitigation: derive solver class from the Modeling agent's flags via the deterministic rule; cross-check.
* **Over/under-resolution or wrong PC (Phase II config)** — a legal but poor configuration that runs slowly or stalls. Mitigation: performance-aware adaptation informed by telemetry; rollback with diagnostics.
* **Verification plan that cannot detect bugs** — e.g., prescribing a test whose expected order the discretization can't exhibit, so a passing test proves nothing. Mitigation: verification-plan sanity check tying expected order to the chosen scheme.
* **Attempted tool use** by the reasoning tool — violates the `forbidTools` contract; server aborts.
