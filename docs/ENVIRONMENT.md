# Runtime environment & setup

> Everything needed to run the PETSc multi-agent system on this machine.
> Host: an **ANL CELS GCE compute node** (Linux 6.8, x86-64).
> Last verified: **2026-07-23** (Session 1).

## Key paths

| What | Path |
|---|---|
| This project | `/home/sarthak.sharma/petsc_mcp_servers_tokamak` |
| Multi-agent system (MCP servers) | `/home/sarthak.sharma/petsc_mcp_servers` (clone of `gitlab.com/petsc/petsc_mcp_servers`) |
| PETSc source + builds | `/home/sarthak.sharma/petsc` (v3.25) |
| Reference physics (non-MCP, Claude Code) | `/home/sarthak.sharma/tokamak` |
| Design proposal (PDF) | `/home/sarthak.sharma/Automated_Problem_to_Solution_Generation_for_PDE_Based_Simulation_Science_10_pages.pdf` |
| Poster abstract template | `/home/sarthak.sharma/USRSE_2026_Posters_Submission_Template.docx` |
| GitHub target | `github.com/engineer-scientist/petsc_mcp_servers_tokamak` |

## Python environment

Use the venv that has the full MCP stack:

```bash
PYVENV=/home/sarthak.sharma/.venvs/mcp-test          # Python 3.12.3
$PYVENV/bin/python --version                         # -> 3.12.3
```

Installed & verified: `fastmcp 3.4.4`, `mcp`, `claude_agent_sdk 0.2.114`.
**Not** installed (only needed by the RAG server, which we do not use): `anthropic`,
`langchain_chroma`, `langchain_nvidia_ai_endpoints`.

To run any server/client/driver, the repo dir must be importable:

```bash
export PYTHONPATH=/home/sarthak.sharma/petsc_mcp_servers
```

## LLM backend — ANL Argo

The agents call Claude through ANL's Argo gateway. Config lives in
`petsc_mcp_servers/petsc_mcp_settings.json` and is auto-applied to `os.environ`
when `petscmcp` is imported (via `_loadSettings`, using `setdefault` so it never
overrides an existing env var):

```json
{ "model": "claudeopus48",
  "env": { "ANTHROPIC_BASE_URL": "https://apps.inside.anl.gov/argoapi",
           "CLAUDE_CODE_SKIP_ANTHROPIC_AUTH": "1",
           "ANTHROPIC_API_KEY": "svcpetsc",
           "PETSC_DIR": "/home/sarthak.sharma/petsc",
           "PETSC_ARCH": "arch-linux-c-opt" } }
```

- `ANTHROPIC_API_KEY=svcpetsc` is the **ANL service account name**, not a secret key
  (auth is skipped; the gateway authorizes by network/identity).
- Model string `claudeopus48` = Claude Opus 4.8 as exposed by Argo.
- **This Claude Code session itself already runs against Argo**, so `claude_agent_sdk`
  spawned by the servers runs *nested* (a `claude` subprocess inside our `claude`
  session). Verified this works (Session 1 smoke test returned `PONG`).

## PETSc builds

| Arch | Kind | Notes |
|---|---|---|
| `arch-linux-c-opt` | CPU, optimized | **default**; compile/run agent uses it. Verified: builds & runs PETSc C programs. |
| `arch-linux-cuda-opt` | CUDA 13.1 + Kokkos 5.1.1, A30 `sm_80` | GPU; batched Landau operator runs here (see `~/tokamak`). |
| `arch-linux-c-debug`, `arch-cpu-debug` | CPU, debug | present |

Compile/run agent working dir: `$PETSC_DIR/$PETSC_ARCH/work`
(= `/home/sarthak.sharma/petsc/arch-linux-c-opt/work`).

## Known gaps / gotchas (must-read)

1. **`python3.13` is hardcoded** in `petscmcp.generateServer()` (the stdio spawn path)
   and in `petsc_servers_startup.sh` / `petsc_servers_test.sh`, but this box only has
   **python3.12**. Impact: only when a server is *spawned via stdio by another server*
   (orchestrator / code-generator fan-out). Workarounds: run servers over **HTTP**
   (`PETSC_MCP_SERVERS_URL=localhost`, generateServer then emits URLs, no python3.13),
   or call the agent async functions directly (our driver does this), or patch to
   `sys.executable`. Direct client use is fine — `MCPDynamicClient` spawns stdio servers
   with `sys.executable`.
2. **PETSc docs are NOT built** — no `arch-linux-c-opt-doc/`. The **documentation server
   will not start** (`RuntimeError: ... documentation was not built`). The code-generator
   server lists documentation + rag as sub-servers, so it must be run without them (or
   docs must be built with `make alldoc`, which is heavy).
3. **RAG server unusable here** — needs `NVIDIA_API_KEY` + a `rag-data/` corpus (absent)
   and langchain deps not installed.
4. **fastmcp is 3.4.4** but the servers were written against `>=2.0.0`. Watch for API
   drift when starting servers as HTTP services (imports of `fastmcp.server.FastMCP`,
   `fastmcp.client.transports` verified importable; full server run not yet re-verified
   this session over HTTP).
5. **Shared compile/run work dir** — all callers share one directory; use unique
   filenames per run to avoid clobbering.

## Quick smoke tests (Session 1, all PASS)

```bash
cd /home/sarthak.sharma/petsc_mcp_servers
P=/home/sarthak.sharma/.venvs/mcp-test/bin/python
E="env PYTHONPATH=$PWD"
# 1) SDK <-> Argo:            returns 'PONG'
# 2) Math Modeling agent:     Grad-Shafranov, time-independent, LaTeX+HTML+UFL
# 3) Numerical Analysis agent: {grid: unstructured, discretization: finite-element} -> DMPLEX, SNES
# 4) compile/run agent:        verified in prior session (mcp_stage1_test.py)
```
