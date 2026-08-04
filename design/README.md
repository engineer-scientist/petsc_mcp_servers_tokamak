# Agent design documents

Design documents for the **AI agents** in this project — the specialist and support agents of
the PETSc multi-agent system (`gitlab.com/petsc/petsc_mcp_servers`) that this project uses, plus
the two agents the proposal names that this project **fills as Phase-I gaps**.

> In this project's vocabulary, **every MCP server is an agent** — see
> `../petsc_mcp_servers/MCPAgents.md`: *"there is nothing to stop an MCP server from using a
> brilliant LLM ... I will refer to MCP servers as agents and implement them to use LLMs when
> appropriate."* So the substrate/knowledge servers get design docs too.

These docs map to the three-layer hierarchy of the design proposal *Automated Problem-to-Solution
Generation for PDE-Based Simulation Science* (McInnes et al., DE-FOA-0003612, Fig. 2). For how
the agents are wired together and driven, see `../docs/ARCHITECTURE.md`; for the changes this
project made to the agents, `../docs/AGENT_SYSTEM_CHANGES.md`.

## The agents

| Proposal layer | Agent | Design doc | Server (port) | LLM? | Status |
|---|---|---|---|---|---|
| Problem Definition | Mathematical Modeling | [Mathematical_Modeling_Agent_Design_Document.md](Mathematical_Modeling_Agent_Design_Document.md) | `pde_modeling_mcp_server.py` (8084) | yes (no tools) | in system |
| Agent Execution | Numerical Analysis | [Numerical_Analysis_Agent_Design_Document.md](Numerical_Analysis_Agent_Design_Document.md) | `na_mcp_server.py` (8085) | yes + rules | in system |
| Agent Execution | HPC Code Generation | [HPC_Code_Generation_Agent_Design_Document.md](HPC_Code_Generation_Agent_Design_Document.md) | `petsc_claude_code_generator_mcp_server.py` (8083) | yes (drives sub-agents) | in system |
| Agent Execution | **Visualization & Analysis** | [Visualization_and_Analysis_Agent_Design_Document.md](Visualization_and_Analysis_Agent_Design_Document.md) | *(gap this project fills; target 8087)* | design intent: yes | **proposed** |
| Workflow Control | Orchestrator | [Orchestrator_Agent_Design_Document.md](Orchestrator_Agent_Design_Document.md) | `orchestrator_mcp_server.py` (8086) + `src/orchestrate_tokamak.py` | yes / driver: no | in system |
| Workflow Control | **Persistent Decision-Aware Memory** | [Persistent_Memory_Agent_Design_Document.md](Persistent_Memory_Agent_Design_Document.md) | *(gap this project fills; `artifacts/` store today)* | no | **proposed** |
| execution substrate | Compile & Run | [Compile_and_Run_Agent_Design_Document.md](Compile_and_Run_Agent_Design_Document.md) | `petsc_compile_run_mcp_server.py` (8080) | no | in system |
| knowledge | Documentation | [Documentation_Agent_Design_Document.md](Documentation_Agent_Design_Document.md) | `petsc_documentation_mcp_server.py` (8081) | no | in system (off this host) |
| knowledge | RAG | [RAG_Agent_Design_Document.md](RAG_Agent_Design_Document.md) | `petsc_rag_mcp_server.py` (8082) | embeddings + rerank | in system (off this host) |

**"Proposed"** = named in the proposal (Fig. 2) but not yet an MCP server in `petsc_mcp_servers`;
this project currently realizes its responsibilities with scripts/stores and these docs specify
how to promote that into an agent.

## The data/control flow

```
                 Orchestrator  ── (Persistent Decision-Aware Memory)
                      │  routes state + artifacts; rollback on failure
   Mathematical  →  Numerical  →  HPC Code      →  Compile & Run  →  Visualization
   Modeling         Analysis      Generation        (build+run)       & Analysis
   (8084)           (8085)        (8083) ───────────┘ (8080)          (proposed)
                                     │ also uses (when available)
                                     └── Documentation (8081), RAG (8082)
```

## The template

Each document follows the proposal's agent-design template:

- **External Design** — Purpose and Goal · Scope · Out of Scope · Inputs · Outputs · Interaction Patterns
- **Internal Design** — Skills List · Tool List · Validation Techniques · Required Logging
- **Additional Information**
- **Failure Modes**

(The Mathematical Modeling doc additionally keeps its authored *Discussion of Formal Models*
section.) Each doc opens with a blockquote mapping the agent to its proposal layer, its concrete
server/port and whether it uses an LLM, and how it shows up in this tokamak project.

## Conventions used to write these

- **Grounded in code, not guesses.** Tools, ports, prompts, caps (`cntlimit`), guards, and
  return schemas are taken from the actual servers in `../petsc_mcp_servers`.
- **Grounded in the proposal** for design intent (the four numbered responsibilities per
  specialist agent, the verification-driven rollback loop, memory/self-improvement).
- **Grounded in this project** for concrete realization (the Grad–Shafranov run, `artifacts/`,
  `figures/`, `src/verify_tokamak.py`, and the upstream fixes in `../docs/AGENT_SYSTEM_CHANGES.md`).
