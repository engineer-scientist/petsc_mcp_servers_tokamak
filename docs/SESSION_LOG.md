# Session log

> Append-only, newest session at the bottom. Each session records: what was done,
> what was verified, and the **exact next step** so any future session resumes cleanly.
> This is the primary "where are we?" document.

---

## Session 1 — 2026-07-23

**Goal.** Understand the multi-agent system, prove it can drive a tokamak PETSc
simulation on this machine, scaffold the project, and plan the deliverables
(US-RSE 2026 poster, Argonne intern presentation, documentation).

**Done.**
- Read the design proposal PDF and mapped its 3-layer hierarchy to the concrete MCP
  servers (see `docs/ARCHITECTURE.md`).
- Inventoried `petsc_mcp_servers`, the PETSc builds, and the reference physics in
  `~/tokamak`. Documented the runtime (see `docs/ENVIRONMENT.md`).
- **Verified the pipeline works on this box (against ANL Argo, nested `claude`):**
  1. `claude_agent_sdk` ↔ Argo (`claudeopus48`) round-trip → returns `PONG`.
  2. **Math Modeling agent** on "Grad-Shafranov equilibrium for tokamak plasma"
     → name = *Grad-Shafranov equation*, time-independent, correct strong+weak form,
     plus MathJax HTML and FEniCS UFL. (Source term `−μ₀R² p′ − F F′` correct.)
  3. **Numerical Analysis agent** on the GS spec → `{grid: unstructured-grid,
     discretization: finite-element}` → `DMPLEX`; nonlinear → `SNES`. Sensible.
  4. compile/run agent: verified in the **prior** session (`mcp_stage1_test.py`):
     create file → `make` (good) → run → `make` (broken) captures compiler stderr.
- Scaffolded this repo: `docs/ src/ artifacts/ poster/ slides/`, git init, remote set
  to `github.com/engineer-scientist/petsc_mcp_servers_tokamak`.

**User decisions (this session).**
- Physics target = **Grad–Shafranov equilibrium, pushing to a shaped real-machine
  equilibrium**. (Chosen refinement: **Cerfon–Freidberg/Solov'ev** family → exact-solution
  verification *and* real-machine look.)
- Orchestration = **project-owned artifact-logging driver + a built-in-orchestrator demo**.

### Session 1 — completion update (end of day 2026-07-23)

**Full pipeline ran end-to-end and produced a VERIFIED simulation.** Canonical run:
`artifacts/run-20260723-113024/` (model claudeopus48, all stages `ok`).
- **Model** → "Grad-Shafranov equation", time-independent (strong+weak+UFL+HTML).
- **Numerical Analysis** → nonlinear → `SNES` (unstructured/FE/DMPLEX suggested).
- **Code Generation** → **267-line PETSc `DMDA`+`SNES` solver** (true Jacobian, ghosted
  residual, parallel error reduction, manufactured-solution check) — **compiled & ran on
  1 and 4 MPI ranks, no human edits** (21 loops, 5 tool calls, 293 s).
- **Verification** (`src/verify_tokamak.py`): max-norm error 8.4e-4 → 2.1e-4 → 5.3e-5 →
  1.3e-5 over 33→65→129→257; **observed order p = 2.00, 2.00, 2.00**;
  `CONVERGED_FNORM_RELATIVE`. Figures: `figures/gs_convergence.png`,
  `figures/gs_flux_surfaces.png`.
- **Metrics** (`src/collect_metrics.py`): 0 solver lines hand-written / 267 generated;
  ~23 LLM completions; ~451 s total wall-clock. See `artifacts/<run>/metrics.md`.

**Transparency (added after review):** the driver now captures, per stage, the exact
agent **input** (`*_input.txt`), the full raw **transcript** (`*_transcript.log` — including
the code-gen ⇄ compile-run inter-agent tool calls), and a per-run **`DATAFLOW.md`** lineage
map; `artifacts/README.md` documents the whole schema. The canonical run was backfilled
with these. The store *is* the proposal's "accumulated structured artifacts".

**Built this session:** `src/orchestrate_tokamak.py` (driver), `src/verify_tokamak.py`,
`src/collect_metrics.py`, `slides/make_slides.py` → `slides/petsc_multiagent_tokamak.pptx`
(10 slides), `poster/abstract.md` + `poster/USRSE26_abstract.docx`, docs (`ARCHITECTURE`,
`ENVIRONMENT`, `USAGE`, `ROADMAP`). **3 upstream fixes** to `petsc_mcp_servers` (branch
`tokamak-improvements`, mirrored in `patches/`): CWD-independent `getScriptPort`, graceful
no-docs/no-RAG code-gen, higher code-gen loop cap + prompt to return after first success.

**Still open.**
- **Push the git repo** to `github.com/engineer-scientist/petsc_mcp_servers_tokamak`
  (user does this; nothing pushed yet).
- **Poster/presenter details**: `poster/abstract.md` and the editable poster
  `poster/USRSE26_poster.pptx` (48×36 in, built by `poster/make_poster.py`) have
  `[PRESENTER ...]` placeholders (name/email/ORCID) to fill; then export to PDF for
  EasyChair (abstract due **Aug 7, 2026**).
- **Slides restyle**: rebuild the deck onto `slides/Argonne_Powerpoint_Template.pptx`
  (user-provided official template).
- **Real-machine shaping**: the current flux-surface figure is the manufactured
  (sine-bump) solution; next add a physical **Solov'ev/Cerfon–Freidberg** equilibrium
  (D-shape, X-point) + q-profile, cross-checked vs the FreeGS reference in `~/tokamak`.
- **Built-in orchestrator demo** (task #5) not yet run.
- Push the `tokamak-improvements` branch upstream (user; it's a fork of gitlab petsc).

**Deliverable polish added later in Session 1 (2026-07-23):**
- `docs/AGENT_SYSTEM_CHANGES.md` — precise before/after of every change vs upstream, and
  `patches/0001–0003` committed (they had been generated into the wrong dir earlier; fixed).
- Poster rebuilt with poster-legible fonts (title 66 / headers 40 / body 30) via a
  two-backend `poster/make_poster.py`; added `poster/USRSE26_poster_preview.png/.pdf`.
- Slides rebuilt via a two-backend `slides/make_slides.py`; added a GitHub-viewable
  `slides/petsc_multiagent_tokamak.pdf` (10 pages). Both generators render a matplotlib
  preview/PDF (no LibreOffice on this host) that stays in sync with the .pptx.
- Note: PDFs can be viewed directly with the Read tool's `pages=` param (no PNG step).

**EXACT NEXT STEP (start here next session) — Task 5: demo the built-in orchestrator.**
> Run the shipped `orchestrator_mcp_server` LLM agent end-to-end on the tokamak problem
> and capture its transcript/artifacts. See `docs/USAGE.md` §4:
> ```bash
> cd /home/sarthak.sharma/petsc_mcp_servers
> env PYTHONPATH=$PWD PETSC_MCP_SERVERS_STDIO=True /home/sarthak.sharma/.venvs/mcp-test/bin/python -c \
>  "import asyncio, orchestrator_mcp_server as o; \
>   print(asyncio.run(o.orchestrate_async('the Grad-Shafranov equilibrium for a tokamak plasma')))"
> ```
> Caveats to expect: it nests deeply (orchestrator → inner Claude → 4 sub-servers, and the
> code generator spawns yet another Claude), so it is slow and may need a retry; the
> orchestrator's `allowed_tools=["mcp__*"]` is ignored by the CLI but bypassPermissions
> covers it; docs/RAG are absent (our graceful-degradation patch handles that). Consider
> capturing its output under `artifacts/orchestrator-<date>/`.
>
> Then (later): restyle slides onto `slides/Argonne_Powerpoint_Template.pptx`; add a
> shaped Solov'ev/Cerfon–Freidberg equilibrium + q-profile (cross-check vs `~/tokamak`
> FreeGS); fill presenter details in `poster/abstract.md` and export the poster to PDF.

**Reproduce the canonical run + verification.**
```bash
cd /home/sarthak.sharma/petsc_mcp_servers_tokamak
env PYTHONPATH=/home/sarthak.sharma/petsc_mcp_servers \
  /home/sarthak.sharma/.venvs/mcp-test/bin/python src/orchestrate_tokamak.py   # full pipeline
env PETSC_DIR=$HOME/petsc PETSC_ARCH=arch-linux-c-opt /usr/bin/python3 src/verify_tokamak.py
/usr/bin/python3 src/collect_metrics.py
```
