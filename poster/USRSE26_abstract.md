<!--
USRSE'26 poster abstract. Structure follows USRSE_2026_Posters_Submission_Template.docx.
Submit as PDF to EasyChair by Friday 2026-08-07. Numbers are filled from the canonical
run's verification.json / metrics.json (see src/verify_tokamak.py, src/collect_metrics.py).
Presenter details filled 2026-08-04. Regenerate the .docx with:
  pandoc poster/abstract.md -o poster/USRSE26_abstract.docx \
    --reference-doc=poster/USRSE_2026_Posters_Submission_Template.docx
-->

# Title

**Automated Problem-to-Solution Generation for a Tokamak Fusion-Plasma Simulation with a Hierarchical Multi-Agent PETSc System**

# Presenters

Sarthak Sharma <ss694@buffalo.edu>, PhD candidate in Computational and Data Sciences, State University of New York at Buffalo, 0009-0009-6746-169X

Dr Junchao Zhang <jczhang@anl.gov>, Division of Mathematics and Computer Science, Argonne National Laboratory, 0000-0003-0367-2358

# Keywords

research software engineering; AI agents for scientific computing; PETSc; partial differential equations; magnetically confined fusion; verification and validation

# Abstract

Building a correct, performant HPC simulation from a scientific idea still demands scarce,
largely implicit expertise in numerical methods and library APIs. We ask whether a
**hierarchical multi-agent AI system** can automate that path for a real
fusion-energy problem, and whether the result can be **verified** rather than merely
plausible.

We use the PETSc multi-agent system (an open set of Model-Context-Protocol "agents":
`gitlab.com/petsc/petsc_mcp_servers`) to generate, from a plain-language description, a
PETSc simulation of the **tokamak Grad–Shafranov equilibrium** — the axisymmetric
ideal-MHD force balance
$\Delta^{*}\psi = -\mu_0 R^2\,p'(\psi) - F F'(\psi)$
that sets the shape of the magnetically confined plasma. The system mirrors the
three-layer architecture of the DOE proposal *Automated Problem-to-Solution Generation
for PDE-Based Simulation Science*: a **Mathematical Modeling** agent, a **Numerical
Analysis** agent, and an **HPC Code Generation** agent that writes, compiles, and runs
PETSc C on the target machine — all driven against Argonne's Argo LLM gateway (Claude
Opus 4.8). A project-owned orchestration driver records every structured
intermediate artifact (model, discretization decision, generated source, build/run logs)
with full provenance, making runs reproducible and resumable.

From the prompt *"the Grad–Shafranov equilibrium for the magnetically confined plasma in
a tokamak,"* the Modeling agent identified the equation and returned its strong and weak
forms; the Numerical Analysis agent selected a nonlinear solve (`SNES`) on a structured
grid; and the Code Generation agent produced a **267-line PETSc program** that
discretizes the Grad–Shafranov operator on a `DMDA` with a true Jacobian and solves it
with `SNES`, including a built-in **method-of-manufactured-solutions** check. The
generated code compiled and ran on **1 and 4 MPI ranks** on an ANL CELS compute node with
**no human edits**. Verification confirms the numerics: the max-norm error is
**2.1×10⁻⁴** on a 65×65 grid and falls to **1.3×10⁻⁵** on 257×257, giving an **observed
order of accuracy p = 2.00** (textbook second order for central differences) under grid
refinement, with `SNES` reporting `CONVERGED_FNORM_RELATIVE`.

We report **decision-gate metrics** — correctness (identified model, compiled/ran,
convergence order), efficiency (wall-clock and LLM/tool calls), and human effort (0 lines
of solver code hand-written) — and we contribute portability and robustness fixes back to
the multi-agent system (CWD-independent server resolution; graceful operation where the
documentation/RAG services are unavailable; a code-generation loop that captures results
reliably). The work is a concrete demonstration that verification-driven, multi-agent
problem-to-solution generation can produce trustworthy HPC simulation code for a
flagship fusion-energy problem.

# References

1. B. Smith, H. Zhang, J. Zhang, S. Balay, L. Chen, M. Keçeli, L. C. McInnes. *Improving usability and productivity of PETSc with agent-based workflows.* 2026. doi:10.13140/RG.2.2.35234.80326.
2. L. C. McInnes et al. *Automated Problem-to-Solution Generation for PDE-Based Simulation Science.* Argonne National Laboratory proposal, DE-FOA-0003612, 2026.
3. S. Balay et al. *PETSc/TAO Users Manual.* ANL-21/39 Rev. 3.25, Argonne National Laboratory, 2026. https://petsc.org
4. PETSc multi-agent MCP servers. https://gitlab.com/petsc/petsc_mcp_servers ; https://mcp.petsc-ai.org
5. H. Grad, H. Rubin. *Hydromagnetic equilibria and force-free fields.* Proc. 2nd UN Conf. on the Peaceful Uses of Atomic Energy, 1958. (Grad–Shafranov equation.)
6. A. J. Cerfon, J. P. Freidberg. *"One size fits all" analytic solutions to the Grad–Shafranov equation.* Physics of Plasmas 17, 032502, 2010.
7. This work: https://github.com/engineer-scientist/petsc_mcp_servers_tokamak

# Connection to Mission, Goals, & Interests of US-RSE Community

Research software engineers increasingly sit between AI code-generation tools and the
trusted, performance-critical libraries that underpin computational science. This
submission speaks directly to that intersection. It is a candid RSE case study of *using*
an agentic system on a real HPC library (PETSc) for a real DOE-mission problem
(fusion-energy plasma), rather than a toy benchmark — including the unglamorous
engineering that makes such systems actually work on a shared compute node: environment
and dependency wrangling, making services degrade gracefully when optional components are
absent, working-directory-independent process spawning, and reproducible,
provenance-tracked runs. We treat **verification as a first-class deliverable**: the
generated simulation is checked against an exact solution and a grid-convergence study,
reflecting the RSE community's emphasis on correctness, testing, and reproducibility over
raw output. Finally, our improvements are contributed **back to the open-source
multi-agent project** as patches, embodying the community's values of open, sustainable,
and collaborative software. We hope the poster sparks discussion about how RSEs can
responsibly adopt, evaluate, and harden AI-assisted workflows for scientific software.
