# AI-for-PDEs: Mathematical (PDE) Modeling Agent

> **Proposal layer:** Problem Definition (McInnes et al., DE-FOA-0003612, Fig. 2 —
> *Mathematical Modeling Specialist Agent*).
> **Concrete realization:** `pde_modeling_mcp_server.py` (port **8084**), an MCP server that
> uses Claude (via `claude_agent_sdk` → ANL Argo, Opus 4.8) with **`petscmcp.forbidTools`**
> so the model reasons but cannot touch the filesystem. Tool: `generate_model(specification)`.
> **In this project:** given *"the Grad–Shafranov equilibrium for a tokamak plasma,"* it
> returns name = *Grad–Shafranov equation*, time-independent, strong + weak form as LaTeX,
> a MathJax HTML page, and FEniCS UFL. See `docs/ARCHITECTURE.md`.

## External Design

**Purpose and Goal**
*Produces a rigorous specification of a complete PDE model (geometry, equations, and boundary conditions), informal representations of the model, and any invariants of the model, maybe other stuff. May produce a hierarchy of models where certain terms, boundary conditions etc are ignored (simplified) etc initially. (We would like these simpler models to also be passed to the NA agent, coder etc. This is how real projects are done and how one gets confidence in the results.) All the information on the hierarchy etc., is retained in the agent data, so one can back up to the simpler models when questions come up on the more complete model.*

Concretely, the agent turns scientific *intent* expressed in natural language (and, in
Phase II, images/video/derived-feature descriptors) into a **well-posed, machine-checkable
PDE/ODE specification** that every downstream agent can consume without re-interpreting the
physics. It is the single owner of "what equation are we actually solving?"

**Scope**
*This is the "what" of the agent's work. What types of work does it do, and are there any specific methods by which that work must be done? This section should contain any concepts or responsibility that are "owned" by this agent.*

* **Elicitation** — extract scientific goals, physical assumptions, geometry, and boundary/initial conditions from the request; ask the user for anything missing that affects well-posedness.
* **Formalization** — produce the strong form *and* the weak/variational form of the model, in three synchronized representations: (1) LaTeX inside a self-contained MathJax HTML page (human-readable), (2) bare LaTeX (portable, for docs/slides/poster), (3) FEniCS **UFL** (machine-readable, a bridge to discretization).
* **Classification** — determine and state explicitly whether the model is **time-dependent** ("the PDE is time-dependent" / "the PDE is not time-dependent"), and name the equation when known ("The name of the PDE is [name]"). These flags drive the Numerical Analysis agent's solver-class choice (TS vs SNES vs KSP).
* **Candidate / hierarchical modeling** — where useful, propose a *hierarchy* of models (e.g., linear Solov'ev source → nonlinear `p(ψ)`, `FF′(ψ)`; homogeneous → shaped boundary) so that simpler, exactly-verifiable rungs can be climbed before the full model. The hierarchy and the provenance of each simplification are retained.
* **Invariants** — can state the conserved quantities / minimization principles a correct solution must respect (e.g., for Grad–Shafranov, force balance / an energy functional), which the Visualization & Analysis agent later checks numerically.

**Owned concepts:** the formal problem statement, modeling choices and their provenance, the
time-dependence and (non)linearity flags, and the model invariants. Anyone needing "the
equation" gets it here — not from the coder's comments or the NA agent's assumptions.

**Out of Scope**

* Does not choose gridding, discretization, or solver approaches (that is the **Numerical Analysis** agent).
* Does not generate, compile, or run code (that is the **HPC Code Generation** and **Compile & Run** agents).
* Does not use tools or the filesystem — it is a pure-reasoning agent (`forbidTools`); any attempt to call a tool is treated as a failure.
* Does not *numerically* verify solutions; it supplies the invariants against which others verify.

**Inputs**
*This describes the information that will flow to this agent. Consider describing what information should/should not be included in a natural language prompt to this agent. If the agent can receive non-textual data (data files, images, etc), describe that here.*

A single `specification` string describing the model in text (Phase II: images, video):

* Geometry (e.g., axisymmetric `(R, Z)` poloidal cross-section for a tokamak).
* Model equations (in words or mathematics).
* Boundary conditions and initial conditions.
* Constraints on the model; whether it satisfies a minimization principle.

**What to include in the prompt:** the physical system and quantity of interest, the domain,
and any known BC/IC. **What to leave out:** discretization/solver preferences, grid
resolutions, PETSc types — those bias the downstream specialists and are out of scope here.
If BC/IC are omitted, the agent should request them rather than silently assume.

**Outputs**
*This describes the information that will flow out of this agent.*

A structured dictionary (the tool's return value) with at least:

| Key | Meaning |
|---|---|
| `request` | the original specification (provenance) |
| `name` | the equation's name if recognized (parsed from `The name of the PDE is [ ... ]`), else `"Unknown"` |
| `time-dependent` | boolean, parsed from the exact phrase the model is required to emit |
| `html` | a complete MathJax HTML page rendering strong + weak form |
| `latex` | bare LaTeX of strong + weak form (no document/section wrapper) |
| `python` | the model in FEniCS **UFL** |
| `full-response` | the model's full text, for audit |

Downstream, the **Numerical Analysis** agent consumes `name`, `time-dependent`, and the
mathematical form; the **HPC Code Generation** agent consumes the equations/BCs; the
**Persistent Memory** agent archives the whole dictionary as the run's model artifact
(`model.json` / `model.html` in `artifacts/<run-id>/`).

**Interaction Patterns**

* May request additional information from the user to fill in details not provided in the initial request (boundary/initial conditions, geometry, whether the problem is time-dependent).
* Normally invoked **first** by the Orchestrator (or the project driver `src/orchestrate_tokamak.py`); its output is routed to the Numerical Analysis agent.
* When a **downstream failure** exposes a modeling gap or invalid assumption (e.g., the solver diverges, or the Visualization agent flags nonphysical output), the Orchestrator routes diagnostics **back to this agent for revision** — the verification-driven rollback the proposal makes a first-class behavior. On rollback the agent can drop to a simpler rung of the model hierarchy.
* Does **not** spawn sub-agents; it is a leaf reasoning agent with no tools.

## Internal Design

**Skills List**
*A skill is a narrowly-defined task always done the same way, possibly deviating from the LLM's training defaults.*

* **Interview / elicitation** — a deterministic back-and-forth to complete an under-specified request (which fields are mandatory for well-posedness; what to ask; when to stop and emit).
* **Three-representation emission** — always produce html + latex + python, each wrapped in a correctly **tagged** triple-backtick fence (` ```html `, ` ```latex `, ` ```python `); never leave a fence untagged (the server extracts by tag).
* **Time-dependence & naming declaration** — always emit exactly one of the two required time-dependence sentences and, when known, the `[bracketed]` equation name, because the server parses these literally.
* **Weak-form derivation** — the standard procedure for going from strong form to a variational statement with the correct function spaces and boundary terms.
* **Model-hierarchy construction** — how to enumerate simplifications (linearization, symmetry reduction, BC simplification) and record why each is valid.
* **Literature grounding** *(future)* — an ordered search procedure (local docs → PETSc/RAG knowledge → web) to confirm the standard form and name of a named equation.

**Tool List**

* **None by design.** The agent runs under `petscmcp.forbidTools`: an LLM completion only, no shell, no web, no file writes. This is a deliberate safety/robustness choice — the model reasons about mathematics and returns text. (Contrast the execution agents, which are allowed the MCP tools.)
* Underlying model: Claude Opus 4.8 via `claude_agent_sdk` → ANL Argo (`claudeopus48`).

**Validation Techniques**

* **Structural self-check** — confirm all three fences are present and correctly tagged and that the required time-dependence sentence was emitted (the server loops up to `maxloops = 3` until it has extracted all three representations).
* **Cross-representation consistency** — the strong form, weak form, and UFL must describe the *same* operator, source term, and BCs (e.g., for Grad–Shafranov the source `−μ₀R² dp/dψ − F dF/dψ` must match across all three).
* **Well-posedness screen** — check that BCs/ICs and the domain are sufficient to determine a unique solution before emitting; otherwise ask.
* **Invariant statement** — where a conservation/minimization principle exists, state it so the Visualization & Analysis agent has a concrete, checkable target.
* **No-tool invariant** — if the model attempts any tool call, the server aborts with `{'failure': 'LLM tried to use tool!'}`; correct behavior never trips this.

**Required Logging**

* Full request and full model response (`full-response`) captured verbatim.
* The parsed flags (`name`, `time-dependent`) and each extracted fence, logged as they are found (the server logs "Found the PDE …" lines).
* In this project the driver additionally persists the input (`model_input.txt`), the raw transcript (`model_transcript.log`), and the structured result under `artifacts/<run-id>/`, and records the model→NA lineage in `DATAFLOW.md` — so any modeling decision is reproducible and auditable.

## Additional Information

* **Why weak form matters here.** Emitting the variational form (and UFL) is what lets the Numerical Analysis agent choose finite elements / DMPLEX cleanly and lets the coder build a `PetscFE` residual; the strong form alone would force the coder to re-derive it.
* **Hierarchy in practice (tokamak).** Rung 1 = Solov'ev linear source (closed-form exact ψ → the verification anchor); Rung 2 = nonlinear `p(ψ)`, `FF′(ψ)` (Newton via SNES); Rung 3 = shaped boundary / X-point (cross-check vs FreeGS). The agent should be able to emit any rung and record how it relates to the others. See `docs/ROADMAP.md` §"Physics ladder".
* **Provenance is a feature.** Retaining the hierarchy and simplification rationale is what allows a later session (or the Orchestrator, on rollback) to "back up to the simpler model when questions come up on the more complete model."

## Failure Modes

* **Under-specified request accepted silently** — inventing plausible BC/IC instead of asking, yielding a well-formed but wrong model. Mitigation: mandatory well-posedness screen + interview skill.
* **Fence/format drift** — an untagged or mis-tagged code fence, or omission of the exact time-dependence sentence, so the server fails to extract a representation (found < 3) or mis-reads time-dependence → wrong solver class downstream. Mitigation: strict emission skill; server retry loop.
* **Cross-representation mismatch** — strong form, weak form, and UFL disagree (wrong sign on a source term, dropped boundary term). Mitigation: consistency self-check before emit.
* **Mis-naming / mis-classifying** — wrong equation name, or calling a nonlinear problem linear. Mitigation: literature-grounding skill; the NA agent's own consistency check as a backstop.
* **Attempted tool use** — violates the `forbidTools` contract; server aborts. (A prompt-injection or an over-eager model could trigger this.)
* **Over-simplification without provenance** — silently dropping a term the physics needs and not recording it, so rollback cannot recover the intent.

## Discussion of Formal Models

I have looked over the current work in formalizing PDE using **Lean** and \*\*Rocq\*\*. In my opinion, Lean is dominated by ODE/PDE theorists, and is mainly focused on abstract settings. For example, they do not have any idea of a Sobolev space because it is mainly useful for computing. The Rocq people, mainly French, seem to be much more focused on numerics. The discussion I found online was [anemic](https://proofassistants.stackexchange.com/questions/379/pdes-and-proof-assistants). I will try to justify these opinions below.

In Lean, there is very little currently having to do with PDE. The main library, MathLib, has a section on [Normed Spaces](https://leanprover-community.github.io/mathematics_in_lean/C12_Differential_Calculus.html#differential-calculus-in-normed-spaces), but no formulation of an actual PDE. The efforts at scientific computing seem [rudimentary](https://lecopivo.github.io/scientific-computing-lean/#) and [underdeveloped](https://github.com/weiran-sun/pde). I am not a fan of [SciLean](https://github.com/lecopivo/SciLean/tree/efbb2d06c81f0f52201d40ee829878bd2d87ac9b/SciLean). However, there is some really interesting stuff, like this [proof of the Nash-Moser Theorem](https://www.scottnarmstrong.com/2026/04/formalizing-de-giorgi-nash-moser-theory-in-lean/). Real analysis in Lean?

The real analysis library for Rocq is called [Coquelicot](https://guillaume.melquiond.fr/doc/14-mcs.pdf). It is the basis of analysis in modern Rocq, and of projects like this [formalization of the integral](https://arxiv.org/abs/2201.03242). There is a group at Paris-Saclay doing things very close to what we want. For example, here is a recent [thesis](https://theses.hal.science/tel-04884651) which formalizes the simplicial Lagrange finite elements, along with the [code repository](https://depot.lipn.univ-paris13.fr/mayero/rocq-num-analysis/-/tree/2.0/), and they have it packaged as a [library](https://rocq-prover.org/p/rocq-num-analysis-fem/2.1.0). Geometry?

UFL - designed for humans to transcribe mathematics to numerics. But we would also like to do math on models and UFL is not great for this. Bit hacky.
