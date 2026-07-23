# The multi-agent system and how we use it

This project **uses** the PETSc multi-agent AI system (`gitlab.com/petsc/petsc_mcp_servers`)
to automatically generate, verify, and run a PETSc simulation of tokamak plasma — the
**magnetohydrodynamics (MHD) fusion problem** that the design proposal
(*Automated Problem-to-Solution Generation for PDE-Based Simulation Science*, McInnes et al.,
DE-FOA-0003612) names as its stretch goal.

## Proposal's 3-layer hierarchy → concrete MCP servers

The proposal (Fig. 2) defines three layers. Each maps to real code in `petsc_mcp_servers`:

| Layer (proposal) | Specialist agent | MCP server (file) | Port | Key tool(s) | LLM? |
|---|---|---|---|---|---|
| **Problem Definition** | Mathematical Modeling | `pde_modeling_mcp_server.py` | 8084 | `generate_model(spec)` → strong/weak form as LaTeX + MathJax HTML + FEniCS UFL, name, time-dependence | yes (no tools) |
| **Agent Execution** | Numerical Analysis | `na_mcp_server.py` | 8085 | `select_approach(spec)` → grid/discretization/integrator; `grid_and_discretization_to_petsc_dm`; `petsc_solver` | yes + rules |
| **Agent Execution** | HPC Code Generation | `petsc_claude_code_generator_mcp_server.py` | 8083 | `generate_code(spec)` → writes/compiles/runs PETSc C, returns code+output | yes (drives compile/run) |
| (execution substrate) | — | `petsc_compile_run_mcp_server.py` | 8080 | `create_file_from_string`, `make`, `run_executable`, `run_bash_command`, `git_grep_petsc_repository` | no |
| (knowledge) | — | `petsc_documentation_mcp_server.py` | 8081 | `get_petsc_manual_pages`, `search`, ... | no |
| (knowledge) | — | `petsc_rag_mcp_server.py` | 8082 | RAG prompts (needs NVIDIA key + data) | yes |
| **Workflow Control** | Orchestrator | `orchestrator_mcp_server.py` | 8086 | `orchestrate(spec)` → drives modeling→NA→codegen→run via an inner Claude | yes (drives 4 servers) |

Not yet present (a **Phase-I gap we fill** — see below):
- **Visualization & Analysis** specialist agent (proposal's 4th execution agent).
- **Persistent, decision-aware memory** of structured artifacts across runs.

`petscmcp.py` is the shared library: settings loading, the dynamic MCP client
(`MCPDynamicClient` — mirrors every server tool as a local method), URL/port helpers,
triple-backtick extraction, `forbidTools` (sandboxed, tool-less options for pure-LLM
agents), and logging.

## How the pieces talk

- **Transport:** streamable-HTTP (default, ports above) or stdio. Servers are RPC
  endpoints; higher-level agents call lower-level ones (orchestrator → the four servers;
  code-generator → compile/run + documentation + rag). This is the proposal's
  "agents = remotely-callable objects" thesis (see `MCPAgents.md`).
- **LLM:** every "brain" agent uses `claude_agent_sdk` → the `claude` CLI → ANL Argo
  (Opus 4.8). Pure-LLM agents (`pde_modeling`, `na`) run with `forbidTools` so the model
  reasons but cannot touch the filesystem; execution agents are allowed the MCP tools only.

## Our usage strategy (this project)

Rather than rely solely on the opaque LLM `orchestrator` (which fans out via stdio and
references the doc/rag servers unavailable here), we drive the **same specialist agents**
from a **project-owned orchestration driver** (`src/`) that:

1. calls each agent in sequence (Model → Numerical Analysis → Code Gen → Verify/Run),
2. **captures every structured intermediate artifact** to `artifacts/<run-id>/`
   (the proposal's "accumulated structured artifacts" + "persistent decision-aware memory"),
3. adds **verification** (manufactured/known solution, convergence, conservation) and
   **rollback/replan** hooks as first-class steps (the proposal's verification-driven loop),
4. is **resumable and logged** so multi-session work continues cleanly.

This is faithful to the architecture (same agents, same tools, same LLM backend) while
being robust, controllable, and provenance-rich — exactly what the poster/paper needs.
We still exercise the built-in `orchestrator` agent as a demonstration where feasible.

## The physics target — tokamak MHD equilibrium (Grad–Shafranov)

The natural, well-posed PDE the pipeline can model, discretize, generate, run, **and
verify** is the **Grad–Shafranov equation** — the axisymmetric ideal-MHD force-balance
that sets the shape of the magnetically confined plasma:

$$ \Delta^{*}\psi \;=\; -\,\mu_0 R^{2}\,\frac{dp}{d\psi} \;-\; F\frac{dF}{d\psi},
\qquad \Delta^{*}\psi \equiv R\,\partial_R\!\Big(\tfrac{1}{R}\partial_R\psi\Big)+\partial_{ZZ}\psi. $$

- It is genuinely the **fusion MHD** problem (poloidal flux ψ, pressure p(ψ), current
  function F(ψ)); its solution gives flux surfaces, the separatrix, and the safety factor q.
- It is **agent-tractable**: elliptic, (generally) nonlinear, time-independent → the NA
  agent already selects finite-element/SNES (unstructured) or finite-difference/SNES
  (structured) correctly.
- It is **verifiable**: the **Solov'ev** profiles (`p′`, `FF′` constant) admit a
  closed-form exact ψ, giving a manufactured-solution convergence test — the proposal's
  headline "verification-driven" evidence.
- It **cross-checks** against the validated FreeGS reference equilibria in `~/tokamak`.

See `docs/SESSION_LOG.md` for status and `docs/ROADMAP.md` for the plan.
