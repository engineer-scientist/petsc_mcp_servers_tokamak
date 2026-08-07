---
geometry: margin=0.6in
fontsize: 10pt
---

<!--
USRSE'26 abstract — source of truth. Rebuild the submission files with:
  cd poster
  pandoc USRSE26_abstract.md -o USRSE26_abstract.docx \
    --reference-doc USRSE_2026_Posters_Submission_Template.docx
  pandoc USRSE26_abstract.md -o USRSE26_abstract.pdf \
    --pdf-engine=xelatex --include-in-header=abstract_header.tex

Revision (2026-08-07): reoriented toward research-software-engineering per reviewer
feedback (J. Zhang, L. C. McInnes) — dropped the "no human edits" narrative, compressed
the physics, added the failure-modes/guardrails theme. Then condensed to fit one page
(compact geometry + 3 tight paragraphs). Title kept per author request.
-->

# Title

**A Multi-agent AI System for Automating Tokamak-Plasma Simulation for Nuclear Fusion Energy.**

# Presenters

- Sarthak Sharma <ss694@buffalo.edu>, PhD candidate in Computational and Data Sciences, State University of New York at Buffalo, 0009-0009-6746-169X.
- Dr Junchao Zhang <jczhang@anl.gov>, Division of Mathematics and Computer Science, Argonne National Laboratory, 0000-0003-0367-2358.

# Keywords

AI agents for scientific computing; research software engineering; multi-agent code generation; verification and validation; reproducibility and provenance; guardrails and human-in-the-loop; PETSc; tokamak Grad–Shafranov equilibria (nuclear fusion).

# Abstract

Building a correct, performant HPC simulation from a scientific idea still demands scarce, largely implicit expertise in numerical methods and library APIs. AI agents can now draft such code, but a draft that *looks* right is not one an engineer can *trust*. We take a research-software-engineering (RSE) view of a real fusion-energy problem: not whether AI can replace that expertise, but what an RSE must build **around** a multi-agent AI system — orchestration, verification gates, provenance, and guardrails — to make its output trustworthy. Using the PETSc multi-agent AI system (Model Context Protocol agents: <https://gitlab.com/petsc/petsc_mcp_servers>), we generate from a plain-language prompt a PETSc simulation of the tokamak **Grad–Shafranov equilibrium** (the force balance that sets a confined plasma's shape). Modeling, Numerical Analysis, and HPC Code Generation agents produce the solver; around them we built a project-owned orchestration driver that records every artifact with full provenance, and a verification harness that gates every result.

We do not treat "it compiled and ran" as success: a grid-refinement study confirms textbook second-order convergence (*p* = 2.00) in MPI parallel — **verification, not the model's confidence, decides acceptance.** The same pipeline then produced one parameterized solver for several real-machine-shaped equilibria (e.g. an ITER-like D-shape and a diverted double-null with magnetic X-points), each verified against an exact analytic benchmark and cross-checked against an independent community code — scaling from the toy anchor to trustworthy shaped cases *without re-architecting the generated solver*.

This was not one-shot magic, and that is the software-engineering story. Running the agents on a shared HPC machine took environment and dependency wrangling, working-directory-independent process spawning, and graceful degradation when optional components are absent — plus **guardrails**: in one instructive failure a hard-coded iteration cap mislabeled a genuinely successful multi-stage run as a failure; we diagnosed it and contributed the fix upstream, one of several. Human effort is not eliminated but **relocated** — from writing solver code to engineering the orchestration, verification, and guardrails that make an AI system's output trustworthy and its failures legible. We report per-run decision-gate metrics (correctness, efficiency, where human effort went). Ongoing work deliberately raises the difficulty (nonlinear profiles, time-dependent/resistive magnetohydrodynamics, 3-D) to map where the system breaks and design the guardrails that keep engineers in control — the focus of the poster.

# References

1. B. Smith, H. Zhang, J. Zhang, S. Balay, L. Chen, M. Keçeli, L. C. McInnes. *Improving usability and productivity of PETSc with agent-based workflows.* 2026. doi:10.13140/RG.2.2.35234.80326.
2. S. Balay et al. *PETSc/TAO Users Manual.* ANL-21/39 Rev. 3.25, Argonne National Laboratory, 2026. <https://petsc.org>.
3. PETSc multi-agent MCP servers. <https://gitlab.com/petsc/petsc_mcp_servers>; <https://mcp.petsc-ai.org>.
4. H. Grad, H. Rubin. *Hydromagnetic equilibria and force-free fields.* Proc. Second UN Conf. on the Peaceful Uses of Atomic Energy, 1958. (Grad–Shafranov equation.)
5. A. J. Cerfon, J. P. Freidberg. *"One size fits all" analytic solutions to the Grad–Shafranov equation.* Physics of Plasmas 17, 032502, 2010.
6. This work: <https://github.com/engineer-scientist/petsc_mcp_servers_tokamak>.

# Connection to Mission, Goals, and Interests of US-RSE Community

Research software engineers increasingly sit between AI code-generation tools and the trusted, performance-critical libraries that underpin computational science. This is a candid RSE case study — not a toy benchmark — of *wrapping* an agentic AI system around a real HPC library (PETSc) for a real DoE-mission problem: the unglamorous engineering that makes such systems work on shared machines, and the guardrails needed when an agent silently does the wrong thing. Our theme is that AI does **not** replace the research software engineer; it relocates the work to orchestration, verification, and guardrails, with **verification as a first-class deliverable**. We hope the poster sparks discussion on how RSEs can responsibly adopt and harden AI-assisted scientific-software workflows.
