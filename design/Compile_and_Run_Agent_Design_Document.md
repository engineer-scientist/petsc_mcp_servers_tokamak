# Compile & Run Agent (PETSc execution substrate)

> **Proposal layer:** execution substrate (not one of Fig. 2's four *specialist* agents, but —
> per this project's `MCPAgents.md`, "I ... will refer to MCP servers as agents" — an agent).
> **Concrete realization:** `petsc_compile_run_mcp_server.py` (port **8080**). **No LLM**: a
> sandboxed bash-like environment with PETSc installed, exposed as MCP tools. It is the hands of
> the system — the only agent that touches files, compilers, and MPI.
> **In this project:** used (indirectly, via the code generator and orchestrator) to compile and
> run the generated Grad–Shafranov solver on 1 and 4 MPI ranks. Working dir:
> `$PETSC_DIR/$PETSC_ARCH/work`. See `docs/ENVIRONMENT.md`, `docs/ARCHITECTURE.md`.

## External Design

**Purpose and Goal**

Provides a controlled place to **create files, compile PETSc C/Fortran programs, run
executables (serial or MPI), and search the PETSc source** — behaving "much like a bash shell"
but with guardrails. It is the execution and quality-check substrate the HPC Code Generation
agent (and the Orchestrator) delegate to; without it, generated code is just text.

**Scope**

* **File creation** — write a program to the work directory from a string (`create_file_from_string`), with a path-traversal guard that confines writes to the work dir.
* **Compilation** — `make` an executable using an auto-generated PETSc makefile (pulls in `${PETSC_DIR}/lib/petsc/conf/variables` + `rules`), optionally with extra source dependencies.
* **Execution** — `run_executable` serially or under MPI (`nsize > 1` via the build's `MPIEXEC`), with an enforced default **20-second timeout** and optional Valgrind.
* **General shell** — `run_bash_command` / `ls` for auxiliary commands, subject to a blocklist.
* **Repository search** — `git_grep_petsc_repository` for fast, indexed source search (the slow `grep -r` is explicitly refused).

**Owned concepts:** the filesystem work area, the build, the process execution, and the safety
policy around them.

**Out of Scope**

* No reasoning or code *generation* — it only builds/runs what it is given.
* No model/method/verification decisions.
* Not a general-purpose shell: dangerous/irrelevant commands are blocked (`sudo`, `su`, `cd`, `pushd`, `popd`, `printenv`, `echo`) and `grep -r` is refused.

**Inputs**

* Tool arguments: filenames + contents, executable/target names, run size/args/timeout, bash strings, search strings.
* Ambient `PETSC_DIR` and `PETSC_ARCH` (checked at startup).

**Outputs**

* Structured results — `{stdout, stderr, returncode}` for bash/make/run; boolean for file creation; a string for `git grep`.
* These results are exactly what the calling agent (code generator/orchestrator) reads to decide "did it compile?" / "did it run?" and to repair errors.

**Interaction Patterns**

* A **leaf** agent: called by higher-level agents (HPC Code Generation always; Orchestrator directly; a future Visualization & Analysis agent for refinement runs). It never calls other agents.
* Callable over streamable-HTTP (default) or stdio; the code generator attaches it as a sub-server. Its Python client wrapper is `petsc_compile_run_mcp_client.PetscCompileRunMCPClient` (used by the code generator for its independent recompile).

## Internal Design

**Skills List**

* **PETSc makefile assembly** — write a correct minimal makefile that includes PETSc's variables/rules and links the target (and any listed dependencies) with the right flags.
* **MPI launch** — parse the build's `MPIEXEC` from `petscvariables`; refuse to run in parallel on a sequential (`--with-mpi=0`) build.
* **Sandbox enforcement** — block the dangerous command set, refuse `grep -r`, and confine file writes to the work dir via `realpath` prefix check.
* **Bounded execution** — always apply a timeout (default 20 s) so a hanging or diverging program cannot wedge the server.

**Tool List**

* `create_file_from_string(filename, file_contents) → bool`
* `make(executable, dependencies='') → {stdout,stderr,returncode}`
* `run_executable(executable, nsize=1, args='', valgrind=False, timeout=20) → {stdout,stderr,returncode}`
* `run_bash_command(string) → {...}` and `ls(path='') → {...}`
* `git_grep_petsc_repository(string) → str`
* **No LLM.** Pure Python + `subprocess`; underlying "model" is N/A.

**Validation Techniques**

* **Return-code propagation** — compile/run failures come back as non-zero `returncode` with captured `stderr`, so callers can detect and react (the code generator's fix loop depends on this).
* **Path-traversal guard** — writes outside the work dir are refused (`create_file_from_string` returns `False`).
* **Command blocklist + `grep -r` refusal** — reject unsafe/pathological commands before executing.
* **Timeout** — bound every run; a timeout returns `returncode = -1` rather than hanging.
* **Startup self-check** — verifies `PETSC_DIR`/`PETSC_ARCH` are set and creates the work dir. (Note: a `make check` self-test exists in the source but is currently stubbed out because running it broke the server after startup — see the code comment.)

**Required Logging**

* Every request and its full result (`stdout`/`stderr`/`returncode`) is logged, including blocked-command and path-traversal attempts and the exact executable command line assembled for a run.
* These logs are captured per-run by the calling agents (e.g., the code-gen ⇄ compile-run transcript preserved in `artifacts/<run-id>/codegen_transcript.log`).

## Additional Information

* **Shared work directory is a known hazard.** All callers share
  `$PETSC_DIR/$PETSC_ARCH/work`; concurrent runs can clobber each other. The source itself flags
  this ("all users share the same directory environment; which is nuts"), and
  `docs/ENVIRONMENT.md` gotcha #5 recommends unique filenames per run. The proper fix is a
  per-caller directory or VM.
* **Portability fix contributed by this project.** `getScriptPort`/`generateServer` were made
  CWD-independent and spawn sub-servers with `sys.executable` so this server can be attached
  correctly from any directory (`docs/AGENT_SYSTEM_CHANGES.md` #1, #2).
* **Security posture.** It runs arbitrary compiled programs by design; risk is bounded by the
  blocklist, path guard, timeout, and the intent to run locally/non-production (cf. the agent
  card's risk notes).

## Failure Modes

* **Work-dir clobbering** — parallel callers overwrite each other's files/executables. Mitigation: unique filenames; per-caller dirs.
* **Parallel run on a sequential build** — `nsize > 1` on a `--with-mpi=0` PETSc; detected and returned as an error rather than crashing.
* **Timeout on a diverging/slow program** — returns `-1`; a caller must not misread this as a compile error (it is a run signal).
* **Makefile/link edge cases** — unusual dependency suffixes or missing sources; surface as non-zero `make` return codes.
* **Sandbox bypass attempts** — blocked-command or path-traversal attempts (logged and refused); an over-broad `run_bash_command` remains the widest surface, mitigated by the blocklist.
* **Startup misconfiguration** — missing `PETSC_DIR`/`PETSC_ARCH` or an un-built arch; the server refuses to start.
