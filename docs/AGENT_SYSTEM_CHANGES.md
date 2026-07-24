# Changes made to the PETSc multi-agent system

This project **uses** the PETSc multi-agent AI system from
[`gitlab.com/petsc/petsc_mcp_servers`](https://gitlab.com/petsc/petsc_mcp_servers) and, as
invited, contributes a small set of **portability and robustness fixes** so the agents run
correctly on an ANL CELS GCE compute node from an external project directory. This file
documents exactly what changed versus the original code.

## Where the changes live

- **Base (upstream) commit:** `acf0632` (`main`, "Merge branch 'barry/add-proposal-agents'").
- **Branch with the changes:** `tokamak-improvements` in the local clone
  `/home/sarthak.sharma/petsc_mcp_servers`.
- **Portable patches** (apply to a fresh clone with `git am patches/*.patch`):
  `patches/0001-Portability-graceful-degradation-*.patch`,
  `patches/0002-getScriptPort-*.patch`,
  `patches/0003-code-generator-*.patch`,
  `patches/0004-orchestrator-*.patch` (in *this* repo).

**Scope:** 3 files, +40 / −9 lines. **No change to the scientific behavior** of the
specialist agents — the Mathematical Modeling and Numerical Analysis prompts/logic are
untouched; these are infrastructure fixes. **Every change is backward-compatible** (default
behavior is preserved when the relevant condition/host matches the original assumptions).

| # | File · function | Change | Why |
|---|---|---|---|
| 1 | `petscmcp.py` · `generateServer` | `python3.13` → `sys.executable` for stdio spawns | host has Python 3.12, not 3.13 |
| 2 | `petscmcp.py` · `getScriptPort` | resolve server scripts in the module's own dir, return an **absolute** path | worked only when CWD was the servers dir |
| 3 | `petscmcp.py` (new) | `documentationAvailable()`, `ragAvailable()` probes | detect optional services |
| 4 | `petsc_claude_code_generator_mcp_server.py` · `generate_code_async` | include only **available** sub-servers; report true server count in the prompt | docs/RAG absent here |
| 5 | `petsc_claude_code_generator_mcp_server.py` · `generate_code_async` | raise message-loop cap `30 → 80`; tell the agent to return after the **first** successful compile+run | thorough agent ran out of loop budget |
| 6 | `orchestrator_mcp_server.py` · `orchestrate_async` | raise iteration cap `35 → 80`; tell the agent to compile+run the program **once** (no degree/rank sweeps) | same failure mode in the top-level orchestrator |

---

## 1. `generateServer`: spawn stdio sub-servers with the running interpreter

**File:** `petscmcp.py` · `generateServer()`

```python
# before
server = {'command': 'python3.13', 'args': [script, '--stdio']}
# after
server = {'command': sys.executable, 'args': [script, '--stdio']}
```

**Why.** When an agent fans out to a sub-server over stdio (the code generator and the
orchestrator do this), the sub-server was launched with a hardcoded `python3.13`. This node
ships **Python 3.12** (the `mcp-test` venv), so the spawn would fail. Using `sys.executable`
launches the sub-server with the same interpreter the parent is running.

**Impact / compatibility.** Works on any host; on a host that genuinely uses `python3.13`
the behavior is identical.

## 2. `getScriptPort`: CWD-independent, absolute-path resolution

**File:** `petscmcp.py` · `getScriptPort()`

```python
# before: globbed the CURRENT WORKING DIRECTORY and returned a basename
scripts = glob.glob('*' + servername + '_mcp_server.py')
script  = os.path.basename(scripts[0])
# after: glob the directory this module lives in; return an absolute path
here    = os.path.dirname(os.path.abspath(__file__))
scripts = glob.glob(os.path.join(here, '*' + servername + '_mcp_server.py'))
if len(scripts) == 0:
    scripts = glob.glob('*' + servername + '_mcp_server.py')   # fallback: CWD
script  = os.path.abspath(scripts[0])
```

**Why (this was the key blocker).** `getScriptPort` located the `*_mcp_server.py` scripts by
globbing the **current working directory** and returned a **basename**. So the fan-out only
worked when the caller ran *from inside* `petsc_mcp_servers`. Run from any other directory
(as our driver does), the glob found nothing, `generateServer` silently fell back to a remote
HTTP URL (`mcp.petsc-ai.org`), the inner Claude received **no** PETSc compile-run tools, and
the code generator produced code it could never compile or run (it reported "the only MCP
tool available is DesignSync"). Searching the module's own directory and returning an
absolute path makes the whole system independent of the caller's CWD.

**Impact / compatibility.** Adds a CWD fallback, so existing "run from the servers dir" usage
still works; every other CWD now works too.

## 3. New probes: `documentationAvailable()` / `ragAvailable()`

**File:** `petscmcp.py` (new functions)

```python
def documentationAvailable() -> bool:
    # True iff $PETSC_DIR/$PETSC_ARCH-doc/manualpages/htmlmap exists (docs were built)
def ragAvailable() -> bool:
    # True iff NVIDIA_API_KEY is set
```

**Why.** The documentation server refuses to start unless the PETSc HTML docs were built
(`make alldoc`), and the RAG server needs an `NVIDIA_API_KEY` + a `rag-data` corpus +
langchain. None of these are provisioned on this compute node. These small probes let
callers decide, at runtime, which optional services to wire up. Used by change #4.

## 4. Code generator: advertise only sub-servers that can actually run

**File:** `petsc_claude_code_generator_mcp_server.py` · `generate_code_async()`

```python
# before: always advertised three sub-servers
mcp_servers = {'PETSc compiler-run': ..., 'PETSc documentation': ..., 'PETSc RAG': ...}
# prompt: "Verify you have access to three MCP servers, if you do not then exit immediately."

# after: include only what's available; report the true count
sub_servers = {'PETSc compiler-run': petscmcp.generateServer('compile_run')}
if petscmcp.documentationAvailable(): sub_servers['PETSc documentation'] = ...
if petscmcp.ragAvailable():           sub_servers['PETSc RAG']           = ...
# prompt: "... there are <N> MCP server(s) available to you); if you do not have the
#          compile-run server then exit immediately."
```

**Why.** The original server always attached the documentation and RAG sub-servers and told
the inner Claude to *exit immediately* unless it saw **three** servers. On a host without
docs/RAG, those servers can't start, so the agent would either bail or waste turns on tools
that error. Now it attaches only servers that can run and states the real count, so the
agent proceeds with just the (essential) compile-run server.

**Impact / compatibility.** On a fully-provisioned host (docs built + `NVIDIA_API_KEY` set),
all three sub-servers are attached exactly as before.

## 5. Code generator: larger loop budget + return after first success

**File:** `petsc_claude_code_generator_mcp_server.py` · `generate_code_async()`

```python
# before
cntlimit = 30
# "... Once the code compiles and runs return the code and its output ..."
# after
cntlimit = 80
# "... As soon as the code compiles and runs successfully ONE time, immediately stop and
#      return ...  Do not test additional numbers of MPI ranks or additional grid sizes ..."
```

**Why.** `cntlimit` caps the number of streamed messages before the server gives up. A
thorough agent that (helpfully) also tested multiple MPI-rank counts and grid sizes exhausted
the 30-message budget **before** emitting its final JSON — so a correct, compiling, *verified*
program was reported as a failure. Observed directly in this project: the agent produced a
working Grad–Shafranov solver (2nd-order convergent) but the run was marked "Too many
iterations." Raising the cap and instructing the agent to return immediately after the first
successful compile+run fixed the capture (a later run finished in 21 loops).

**Impact / compatibility.** Purely a budget/prompt change; correct behavior on quick programs
is unchanged.

## 6. Orchestrator: larger iteration budget + run the program once

**File:** `orchestrator_mcp_server.py` · `orchestrate_async()`

```python
# before
cntlimit = 35
# "... then use the PETSc compile and run MCP server. When you have completed the
#      orchestration send back the message "I have completed the orchestration"."
# after
cntlimit = 80
# "... then use the PETSc compile and run MCP server to compile and run the generated
#      program exactly once (do not test additional MPI rank counts, polynomial degrees,
#      or grid sizes). As soon as the program has compiled and run successfully one time,
#      immediately send back the message "I have completed the orchestration"."
```

**Why.** This is the same failure mode as change #5, one level up. The orchestrator counts
**every** streamed SDK message — assistant text, each tool-use, and each tool-result — against
one `cntlimit`. A faithful four-stage run (modeling → numerical analysis → code generation →
compile/run), in which the inner agent also retried a numerical-analysis tool and then
announced it would sweep P1/P2 elements and 1/2 MPI ranks, hit 35 messages **exactly as it
issued its first `run_executable`**. Observed directly in this project
(`artifacts/orchestrator-20260724/`): the generated DMPLEX + PetscFE solver **compiled
cleanly and had already converged** (`CONVERGED_FNORM_RELATIVE`, 741 DOFs), yet the run
returned `{'failure_message': 'Too many iterations 36 of orchestration.'}`. Raising the cap to
80 and telling the agent to run once let the very next run finish cleanly with
`I have completed the orchestration` (`artifacts/orchestrator-20260724-fixed/`).

**Impact / compatibility.** Purely a budget/prompt change; the four-stage sequence and the
`bypassPermissions` fan-out are unchanged.

---

## Observed but *not* changed (candidate future fixes)

- **`allowed_tools` pattern.** The code generator and orchestrator pass
  `allowed_tools=["mcp__PETSc*"]` / `["mcp__*"]`. Claude Code 2.x rejects these wildcard
  allow-patterns (`Ignoring --allowedTools rule ...`), but because the agents run with
  `permission_mode="bypassPermissions"` the tools still execute, so it is currently
  harmless. A precise fix would enumerate `mcp__<server>__<tool>` names or rely solely on
  bypass mode.
- **Compile-run work directory.** The compile-run server uses `$PETSC_DIR/$PETSC_ARCH/work`.
  We considered making this configurable (to keep scratch out of the shared PETSc tree) but,
  per the maintainer's preference, left it unchanged.

## What this project added *around* the system (not modifications to it)

These live in this repo, not in `petsc_mcp_servers`, and do not modify the agents:
`src/orchestrate_tokamak.py` (a project-owned driver that calls the real agents and records
provenance + full transcripts), `src/verify_tokamak.py`, `src/collect_metrics.py`, and the
`artifacts/` store. See `docs/ARCHITECTURE.md`.
