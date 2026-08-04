# Visualization & Analysis Agent

> **Proposal layer:** Agent Execution (McInnes et al., DE-FOA-0003612, Fig. 2 —
> *Visualization / Analysis Specialist Agent*; responsibilities: scientific rationale,
> diagnostic signals, human understanding, automated refinement).
> **Status:** a **Phase-I gap this project fills** — there is **no MCP server for it yet** in
> `petsc_mcp_servers` (see `docs/ARCHITECTURE.md` "Not yet present"). This document is
> therefore **design-forward**: it specifies the agent and grounds it in the concrete
> post-processing this project already performs by hand.
> **Current realization in this project (to be agent-ified):** `src/verify_tokamak.py`
> (convergence/order-of-accuracy + conservation), the figures `figures/gs_convergence.png`,
> `figures/gs_flux_surfaces.png` (+ planned q-profile), and the FreeGS cross-check in
> `~/tokamak`. Target port when built: **8087** (next free after the orchestrator's 8086).

## External Design

**Purpose and Goal**

Converts raw simulation outputs into **interpretable evidence** (figures, tables) *and*
**diagnostic signals** that drive human understanding and automated refinement. Per the
proposal it performs visualization-pipeline generation, feature/analysis selection, rendering
configuration, and **diagnostic extraction** — conservation checks, instability indicators,
anomaly signals, and quantitative summaries. Crucially, it is the system's **evaluator**: when
analysis reveals inconsistency, nonphysical behavior, or mismatch with expected patterns, it
emits signals that **trigger rollback** to earlier stages. (The proposal even describes using
this agent as the evaluator in an AlphaEvolve-style feedback loop.)

**Scope**

* **Visualization pipeline generation** — produce ParaView Python scripts and/or VTK-based C++/Python processing pipelines (and, for this project's lightweight cases, matplotlib figures) from the simulation output and the model's geometry.
* **Feature & analysis selection** — choose the diagnostics that matter for *this* model: e.g., for Grad–Shafranov, flux-surface contours of ψ, the separatrix/X-point, the safety factor `q(ψ)` profile, and the magnetic axis.
* **Rendering configuration** — colormaps, contour levels, axes, viewport, and layout (accessible, publication-quality; see the repo's `dataviz` conventions).
* **Diagnostic extraction (the evaluator role)** — compute quantitative correctness/consistency signals: **observed order of accuracy** from a grid-refinement sequence (MMS), **conservation residuals**, instability/anomaly indicators, and summary norms.
* **Evaluation signal emission** — return a pass/fail + numeric diagnostics to the Orchestrator, with enough context to localize the blame (model? discretization? code?).

**Owned concepts:** visual products, quantitative diagnostics, and the "is this result
trustworthy / physical?" verdict fed back into the workflow.

**Out of Scope**

* Does not generate solver code (HPC Code Generation) or run it (Compile & Run) — it consumes the *outputs* of those.
* Does not choose the numerical method or prescribe the verification *plan* (that is the Numerical Analysis agent); it **executes and evaluates** that plan and reports the result.
* Does not decide control flow; it emits signals and the Orchestrator decides whether to rollback.

**Inputs**

* Simulation outputs: solution fields (ψ on the grid), residual/convergence history, run stdout, and any output files the program wrote.
* The **model context** (geometry, invariants/expected conservation, exact/manufactured solution) from the Mathematical Modeling agent, and the **verification plan** (refinement sequence, expected order) from the Numerical Analysis agent.
* A reference for cross-checking when available (here: FreeGS equilibria in `~/tokamak`).

**Outputs**

* **Visual products** — figures/animations (e.g., flux-surface plot, convergence plot, q-profile) and the scripts that generate them.
* **Quantitative diagnostics** — a structured record, e.g. `{max_norm_error[], observed_order[], conservation_residual, converged_reason, ...}`. In this project the analogue is `figures/gs_verification.json` (grids, spacings `h`, errors, and the three `log2` order estimates → **p = 2.00, 2.00, 2.00**; see `docs/VERIFICATION.md`).
* **Evaluation signals** — a verdict (`ok` / `nonphysical` / `not-converged` / `wrong-order`) plus diagnostics for rollback.

**Interaction Patterns**

* Invoked by the Orchestrator/driver **after** a successful compile+run, as the final execution-layer stage.
* **Feedback edge:** its evaluation signals flow back to the Orchestrator, which may **rollback** to Numerical Analysis (wrong order / instability) or Mathematical Modeling (nonphysical result / violated invariant) — the closed loop that distinguishes this proposal ("verification-driven, with validation, rollback, and diagnostic feedback as first-class components").
* May act as a **client of the Compile & Run agent** to launch additional runs (e.g., the grid-refinement sweep that MMS requires) and, in Phase II, of the Documentation/RAG agents for method context.
* When built as an LLM-driven MCP server, it would (like the code generator) drive an inner agent to author the ParaView/VTK pipeline and then execute it via the Compile & Run agent.

## Internal Design

**Skills List**

* **MMS convergence study** — given a manufactured/known exact solution, run a refinement sequence, measure error at each level, and compute `p = log2(e_h / e_{h/2})` (as `src/verify_tokamak.py::orders()` does); compare against the discretization's design order.
* **Conservation / invariant check** — evaluate the invariants the Modeling agent supplied (force balance, energy, mass) and report residuals.
* **Diagnostic pipeline authoring** — emit ParaView Python / VTK pipelines (Phase II) or matplotlib scripts (Phase I) parameterized by the model's fields and geometry.
* **Domain-specific feature extraction** — tokamak specifics: flux-surface contouring, separatrix/X-point detection, magnetic-axis location, `q(ψ)` computation.
* **Reference cross-check** — align and compare against an external validated solution (FreeGS) with tolerances.
* **Anomaly detection** — flag NaN/Inf, non-monotone residuals, wrong convergence order, or values outside physical bounds, and map each to the most likely upstream cause.
* **Accessible rendering** — apply the project's visualization conventions (colorblind-safe palettes, labeled axes, light/dark consistency).

**Tool List**

* *(When built)* exposes tools such as `analyze(outputs, model_context) → diagnostics`, `visualize(outputs, model_context) → figures/scripts`, `convergence_study(spec) → orders`.
* Client access to the **Compile & Run** agent for refinement runs; **ParaView/VTK** and **matplotlib** for rendering; NumPy for the numeric diagnostics.
* If LLM-driven, Claude via `claude_agent_sdk` → ANL Argo, under `bypassPermissions` with only the needed sub-servers (mirroring the code generator's provisioning pattern).

**Validation Techniques**

* **Self-consistency of the study** — expected order must match the scheme (central FD ⇒ 2); a measured order far from expected is reported as a *finding*, not silently accepted.
* **Independent recomputation** — diagnostics are computed from the run outputs themselves (not from anything the LLM asserted), so the verdict is a property of the data. This is the "independent of where the code came from" argument in `docs/VERIFICATION.md`.
* **Reference agreement** — where a validated reference exists, require agreement within tolerance before declaring `ok`.
* **Figure sanity** — verify a rendered figure actually contains the expected features (e.g., closed flux surfaces, a separatrix) rather than an empty/degenerate plot.

**Required Logging**

* The diagnostics record (errors, orders, conservation residuals, converged reason) as machine-readable JSON (cf. `figures/gs_verification.json`).
* The exact analysis/visualization scripts and their parameters (reproducibility).
* The evaluation verdict and, on failure, the rollback recommendation + evidence.
* Archived by the Persistent Memory agent under `artifacts/<run-id>/` alongside the figures.

## Additional Information

* **This is the missing evaluator that closes the loop.** Without it, "it compiled and ran" is
  the strongest claim the pipeline can make. With it, the pipeline can claim "it is *correct*"
  (verified order of accuracy, conserved invariants) — the headline of the poster/talk.
* **Why it is currently scripts, not an agent.** In Phase I this project realizes the agent's
  responsibilities deterministically (`src/verify_tokamak.py` + figure generators) so results
  are trustworthy and cheap; the design intent is to promote this into an MCP server (proposal's
  4th execution agent) so the Orchestrator can call it and act on its signals automatically.
* **Roadmap tie-in.** Adding this MCP server is listed in `docs/ROADMAP.md` §"Improvements to
  the multi-agent system" and milestone #4/#9 (q-profile + shaped-equilibrium diagnostics).

## Failure Modes

* **False "ok" on a plausible-but-wrong result** — accepting output that looks reasonable but fails a convergence or conservation test. Mitigation: always run the prescribed MMS/convergence study and invariant checks; never pass on visuals alone.
* **Wrong-order misattribution** — measuring the wrong order because the *test* is mis-set (e.g., boundary sampled at the wrong points), not because the solver is buggy. Mitigation: study self-consistency check; verify against a known exact case first.
* **Degenerate/misleading figures** — empty contours, saturated colormaps, or wrong aspect ratio that hide features. Mitigation: figure-sanity skill + accessible rendering conventions.
* **Reference mismatch from alignment, not physics** — disagreeing with FreeGS because of differing normalization/geometry, not a real error. Mitigation: careful alignment + documented tolerances.
* **Silent numerical failure** — NaN/Inf or non-converged runs treated as data. Mitigation: anomaly detection gates the diagnostics.
* **Rollback thrash** — emitting conflicting signals that bounce work between Modeling and NA. Mitigation: localize blame with specific evidence so the Orchestrator can pick one target.
