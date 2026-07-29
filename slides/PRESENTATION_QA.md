# Anticipated audience Q&A — "Multi-Agent AI System for PETSc Simulation of Plasma in a Tokamak"

**Event:** ANL Learning Off The Lawn · **Advisors likely present:** Dr Junchao Zhang (PETSc, GPU,
communication), Dr Lois Curfman McInnes (PETSc, proposal PI), Prof Matt Knepley (author of
DMPlex / PetscFE). Tailor tone accordingly — some of these questions will come from the people
who *wrote* the code you are demoing.

---

## 0. Cheat-sheet — the numbers to have on the tip of your tongue

| Thing | Value | Which run |
|---|---|---|
| PDE | Grad–Shafranov (axisymmetric ideal-MHD equilibrium), Solov'ev profiles | both |
| Discretization — run A | **DMDA + SNES**, 2nd-order central finite differences, analytic ("true") Jacobian | project-driver run |
| Discretization — run B | **DMPLEX + PetscFE** (P1 Lagrange finite elements) | built-in orchestrator run |
| Solver | PETSc **SNES** (Newton), converged `CONVERGED_FNORM_RELATIVE` | both |
| Verification | Method of manufactured solutions; **observed order p = 2.00, 2.00, 2.00** | run A |
| Finest-grid error | max-norm **1.32×10⁻⁵** on 257², L₂ 1.62×10⁻⁵ | run A |
| Grid / DOFs | 65²→257² refinement (run A); 225 DOFs, ‖ψ‖₂ = 2.04 (run B) | — |
| Parallel | compiled & ran on **1 and 4 MPI ranks**, no human edits | run A |
| Human effort | **0 lines of solver code hand-written**; 267 lines AI-generated | run A |
| End-to-end cost | **≈ 450.8 s** wall-clock; code-gen 21 loops / 5 tool calls; ≈ 23 LLM completions | run A |
| LLM backend | **Claude Opus 4.8 via Argonne's Argo gateway** (internal — no external data egress) | both |
| Upstream contributions | **4 robustness fixes** to `petsc_mcp_servers` (3 files, +40/−9), incl. a real false-failure bug | — |

**One-sentence framing if you get stuck:** *"The point isn't a new Grad–Shafranov solver — it's
that a multi-agent AI system took one English sentence to a compiled, parallel, and
independently-**verified** PETSc solver with zero hand-written solver code, and I can prove the
answer is right, not just plausible."*

---

## 1. THE question you already got — DMDA vs DMPLEX

**Q (Junchao already asked this): Why does "The AI pipeline in action" say DMDA, but "Fully
autonomous: the built-in orchestrator" says DMPLEX? Is something inconsistent?**

**A:** Nothing is wrong — those are two *different runs* of the system through two *different
orchestration paths*, and each independently chose a valid discretization for the same problem.
- The **project-driver run** produced a **DMDA + SNES** finite-difference solver (structured
  grid). That's the run behind slides 5–8 (pipeline, code excerpt, verification, metrics).
- The **built-in LLM orchestrator run** independently chose a **DMPLEX + PetscFE** finite-element
  solve (unstructured mesh). That's slide 9.
- I verified both against the generated C: `DMDACreate2d` / `DMDA_STENCIL_STAR` in the first,
  `DMPlexCreateBoxMesh` / `PetscFECreateLagrange` / `DMPlexSetSNESLocalFEM` in the second.

**Turn it into a selling point:** *"This is actually evidence the system isn't hard-wired to one
recipe — given the same physics, two paths made two legitimate, standard PETSc choices:
finite differences on a structured grid, and finite elements on an unstructured mesh. Both
compiled and ran with no human edits."*

*(You said you'll add a label to each slide making the "run A / run B" distinction explicit —
good; that removes the ambiguity Junchao spotted.)*

---

## 2. Verification & correctness (expect the hardest questions here)

**Q: How do you actually know the answer is correct, and not just plausible?**
**A:** Method of manufactured solutions. Solov'ev profiles (dp/dψ and F dF/dψ constant) admit a
closed-form exact ψ, so I impose a known solution, derive the forcing, and measure the error as
the grid refines. The observed order of accuracy is **2.00, 2.00, 2.00** — exactly the design
order for 2nd-order central differences. A wrong-but-plausible solver would not converge at the
theoretical rate. That's the "trustworthy, not just plausible" claim made concrete.

**Q: The generated code might just be a memorized PETSc example. How is verification meaningful
then?**
**A:** Verification is independent of where the code came from — the convergence rate is a
property of the discretization on *this* problem, and I compute it from the runs, not from the
LLM's claims. On top of that I read the generated source, and the two runs produced genuinely
different implementations (FD vs FE), which a single memorized snippet wouldn't.

**Q: You used a `true`/analytic Jacobian — hand-derived by the agent, or `-snes_fd`?**
**A:** The agent wrote an **analytic Jacobian** (`FormJacobian` passed to `SNESSetJacobian`), not
finite-difference or coloring. That's both a correctness signal (the residual and Jacobian are
consistent — Newton converges cleanly) and an efficiency one.

**Q (sharp, likely from Knepley): Solov'ev profiles make the source linear in ψ — so why a
*non*linear solver (SNES) at all?**
**A:** Correct — for constant p′ and FF′ the source is independent of ψ, so it's effectively a
linear elliptic solve and SNES converges in one Newton step. The agent selected SNES as the
*general* Grad–Shafranov path, which is the right call: the same code handles genuinely nonlinear
p(ψ), F(ψ) profiles with no change. For the verification test the linear case is deliberate —
it gives a clean, closed-form manufactured solution.

**Q: Did you cross-check the physics against anything real?**
**A:** Yes — I keep a separately hand-built, validated FreeGS-based stack as a physics reference
for Solov'ev/Cerfon–Freidberg equilibria. The MCP pipeline's job here is the *automation and
verification* story; the FreeGS stack is the independent physics sanity check.

---

## 3. The multi-agent system — how it works

**Q: What are the agents, concretely?**
**A:** Four specialist MCP servers mapping to the proposal's 3-layer hierarchy:
(1) **Mathematical Modeling** — English → governing equation, strong/weak form, time-dependence;
(2) **Numerical Analysis** — grid, discretization, solver (SNES) choice;
(3) **HPC Code Generation** — writes, compiles, and runs PETSc C;
(4) **Compile-and-Run** — the execution substrate (make/run on the real machine).
A separate **Orchestrator** agent can drive all four on its own (that's the "fully autonomous"
slide). Each "brain" agent is Claude Opus 4.8 via Argo.

**Q: What's the difference between your driver and the built-in orchestrator?**
**A:** Same agents, same tools, same LLM — two ways to coordinate them.
- My **project-owned driver** calls the agents in sequence and records every intermediate
  artifact with provenance, adds the verification step, and is resumable/logged — controllable
  and reproducible, which is what a poster/paper needs.
- The **built-in orchestrator** is the shipped LLM that sequences the four servers itself from
  just the prompt — more autonomous, less controllable. I demo both.

**Q: Where does the LLM run? Is our data leaving the lab?**
**A:** No. Everything runs through **Argonne's internal Argo gateway** (Opus 4.8). No external API
calls, no data egress — which matters for a lab setting.

**Q: What stops the LLM from hallucinating a solver that looks right but isn't?**
**A:** Two hard gates that don't depend on the model's opinion: the **real compiler and runtime**
(code that doesn't compile or run is caught by PETSc/`make`, not by the LLM saying it's fine),
and **numerical verification** (MMS convergence catches plausible-but-wrong). The LLM proposes;
the compiler and the convergence test dispose.

**Q: How reproducible is a run? LLMs are stochastic.**
**A:** Individual generations vary — that's exactly why the two runs chose different
discretizations. I make the *evidence* reproducible: the driver captures every artifact,
transcript, and the exact model/prompt to `artifacts/<run-id>/`, and verification is
deterministic given the generated code. The claim I stand behind is "verified correct," not
"bit-identical every time."

---

## 4. Your contributions (be ready — advisors care about this)

**Q: What did you actually contribute versus just running an existing system?**
**A:** Three things: (1) the **first end-to-end fusion-MHD demonstration** of this pipeline —
prompt to verified, parallel Grad–Shafranov solver; (2) a **verification-driven driver** that
adds manufactured-solution testing, provenance, and resumability around the agents; and (3)
**4 upstream robustness fixes** to `petsc_mcp_servers` (3 files, +40/−9 lines, no change to the
agents' scientific behavior).

**Q: Tell me about the bug you found in the orchestrator.**
**A:** The orchestrator counted *every* streamed message — assistant text, tool calls, tool
results — against one hard iteration cap of 35. A faithful four-stage run hit the cap *exactly
as it issued its first run command*, so a solver that had **already compiled and converged** was
reported as "Too many iterations" — a false failure. I raised the cap and told the agent to
compile-and-run once; the next run finished cleanly. Same failure mode existed one layer down in
the code generator. Both are in `patches/` and documented in `docs/AGENT_SYSTEM_CHANGES.md`.

**Q: Why were the other fixes needed?**
**A:** Portability so the agents run from an external project directory on this node — e.g. a
hardcoded `python3.13` (this node has 3.12), and a script-lookup that only worked when you ran
from inside the servers directory (otherwise it silently fell back to a remote URL and the
code generator got no compile tools at all). All backward-compatible.

---

## 5. Physics / fusion questions (general audience)

**Q: What is the Grad–Shafranov equation, in one breath?**
**A:** The axisymmetric ideal-MHD force balance — it's what you get when you balance the plasma
pressure gradient against the magnetic (J×B) force in a tokamak. Solving it gives the poloidal
flux ψ(R,Z), and from ψ the flux surfaces, the magnetic axis, and the safety factor q.

**Q: Is this a real tokamak equilibrium?**
**A:** It's a **Solov'ev analytic equilibrium** — an idealized, well-posed case chosen because it
has a closed-form solution I can verify against. Real-machine shaping (D-shaped boundary, an
X-point, a realistic q-profile) is the next step; the point of this stage was the verified
automation pipeline, not a device-specific equilibrium.

**Q: Does this do transport / turbulence / time-dependent MHD?**
**A:** No — this is the static **equilibrium** (force balance), which is time-independent. Transport
and gyrokinetic turbulence are separate, much larger problems. Equilibrium is the natural first
target: well-posed, elliptic, nonlinear, and verifiable.

**Q: What's the safety factor q and did you compute it?**
**A:** q is roughly how many times a field line goes the long way around the torus per poloidal
loop — it governs MHD stability. It's derivable from the flux surfaces I compute; a proper
q-profile is part of the real-machine-shaping next step, not this verification run.

---

## 6. Scale, performance, HPC

**Q: How big / how parallel did you actually run?**
**A:** I demonstrated correctness and MPI-parallel execution on 1 and 4 ranks, on grids up to
257². The discretizations (DMDA, DMPlex) are distributed-memory scalable by construction in
PETSc — I demonstrated the *mechanism*, not a hero-scale run. Larger and GPU runs are
straightforward next steps (there's an A30 arch available).

**Q: 450 seconds seems slow for a Poisson-like solve.**
**A:** That 450 s is the **whole generation pipeline** end-to-end — LLM reasoning plus compilation
plus the run — not the solve. The actual PETSc solve is milliseconds. The number to read is "one
English sentence to a verified parallel solver in under eight minutes, zero human solver code."

**Q (Junchao asked this): Does the 450.8 s include the program's execution time?**
**A:** Yes, but nested and negligible. It's the sum of three timed agent stages:
model **92.5 s** + numerical-analysis **65.5 s** + code-generation **292.8 s** = **450.8 s**. The
compile *and* the run happen inside the 292.8 s code-gen stage (the code-gen agent drives the
compile-run tool and loops until one successful compile+run; `codegen_output.txt` is the running
program's stdout). Two caveats to state up front: (1) the execution time is a tiny fraction — the
292.8 s is dominated by **LLM latency over Argo (21 loops) and compilation**, while the linear
Solov'ev solve on 65² is milliseconds; (2) it does **not** include the separate multi-grid
**verification sweep** (33/65/129/257), which `verify_tokamak.py` ran afterward, outside the three
timed stages. It also excludes PETSc's own build and server startup.

**Q: Did you use the GPU?**
**A:** Not for these runs — they used the CPU-optimized PETSc arch. A CUDA arch is available and
DMDA/DMPlex + SNES carry over to GPU; it wasn't the focus of the verification story.

---

## 7. Skeptical / big-picture

**Q: Why not just use FreeGS or an existing GS solver? Why generate one?**
**A:** The goal isn't a better Grad–Shafranov code — GS is the *testbed*. It's the well-posed,
verifiable PDE I use to show the automated generation-and-verification methodology works on a
real fusion problem. FreeGS is my independent physics cross-check, not the deliverable.

**Q: Is this going to replace computational scientists?**
**A:** No — it removes the boilerplate between a physics statement and a first correct, parallel,
verified solver. The scientist still sets the problem, decides what "correct" means, and owns the
verification. What changed is that the tedious, error-prone translation step got faster and
came with a built-in proof-of-correctness.

**Q: How much of this was AI vs you?**
**A:** The **solver was 0 hand-written lines** — fully AI-generated, compiled, and run. The
*scaffolding* around it is my engineering: the verification harness, the provenance driver, the
physics cross-check, the upstream fixes, and the analysis. The AI writes the solver; I make the
result trustworthy and reproducible.

**Q: What are the limitations / what would break this?**
**A:** Honest list: (1) verified on an idealized Solov'ev equilibrium, not a shaped real-machine
one yet; (2) demonstrated at modest scale, not hero runs; (3) it depends on the problem being
one the modeling agent can pin down and that has a verification handle — MMS won't always be
available; (4) the built-in orchestrator is less controllable than my driver. Each is a named
next step, not a dead end.

**Q: What's next?**
**A:** Real-machine shaping (D-shape, X-point, q-profile) with the FreeGS cross-check; larger and
GPU-scaled runs; adding the proposal's fourth execution agent (Visualization/Analysis); and
broadening beyond GS to other verifiable PDE classes.

---

## 8. If you don't know an answer

Say so cleanly and offer the follow-up — in this room that reads as competence, not weakness:
*"I haven't measured that — let me get the number and follow up."* Especially safe for: exact
strong scaling, GPU timings, memory footprint, and anything about device-specific equilibria you
haven't run yet. Do **not** invent a number in front of the people who built PETSc.
