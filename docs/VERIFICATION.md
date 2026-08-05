# Verification: the "order of accuracy p = 2.00, 2.00, 2.00" slide

This document explains the verification slide in the presentation
(`slides/make_slides.py`, slide 8) and what the headline number
**"Observed order of accuracy p = 2.00, 2.00, 2.00"** actually means.

The claim on the slide is: *the generated Grad–Shafranov solver isn't just
producing plausible-looking output — it is provably solving the equation
correctly.* The evidence is a **method of manufactured solutions (MMS)**
convergence study.

## What "order of accuracy" means

The solver discretizes the Grad–Shafranov PDE on a grid with spacing `h` (the
distance between grid points). Any discretization has a **truncation error**
that shrinks as the grid refines. The *order of accuracy* `p` says **how fast**
it shrinks:

    error ≈ C · h^p

- `p = 1` → halve the grid spacing, error drops ~2×.
- `p = 2` → halve the grid spacing, error drops ~4× (each refinement helps a lot).

The code uses **central finite differences**, whose theoretical design order is
exactly 2. The test asks: *does the solver actually achieve the 2nd-order
convergence it is supposed to?*

## Method of manufactured solutions (why the error is knowable)

Normally you can't measure the true error because you don't know the exact
answer. MMS removes that problem:

1. Choose Solov'ev profiles (`dp/dψ` and `F dF/dψ` constant), which admit a
   **closed-form exact ψ**.
2. Impose that known ψ and derive the forcing term it requires.
3. Solve numerically on a sequence of grids and measure the error against the
   known exact ψ at each resolution.

The Solov'ev/linear source is chosen deliberately: it gives a clean,
closed-form manufactured solution, which makes it a rigorous verification
anchor.

## How the number is computed

With a known exact ψ we measure the true error at each resolution, then compute
`p` between consecutive grids (`src/verify_tokamak.py`, `orders()`):

    p = log(e_h / e_{h/2}) / log(h / (h/2)) = log2(e_h / e_{h/2})

Actual run data (`figures/gs_verification.json`, run `run-20260723-113024`):

| Grid | Spacing `h` | Max-norm error |
|------|-------------|----------------|
| 33²  | 0.0625      | 8.44 × 10⁻⁴ |
| 65²  | 0.03125     | 2.11 × 10⁻⁴ |
| 129² | 0.015625    | 5.27 × 10⁻⁵ |
| 257² | 0.0078125   | 1.32 × 10⁻⁵ |

Each grid halving drops the error by ~4×. Taking `log2` of each successive
error ratio gives **three** values (one per pair of consecutive grids):
`2.0004, 2.0001, 2.0000` → rounded, **2.00, 2.00, 2.00**.

That is why there are **three** numbers, not one: there are three refinements
(33→65, 65→129, 129→257), each yielding one measured `p`. All three land
essentially exactly on the theoretical value of 2.

## Why this matters for the presentation's argument

- A solver with a bug in the operator, boundary conditions, or Jacobian would
  typically converge at the *wrong* rate (or not converge cleanly), even if its
  output looked reasonable. Hitting 2.00 three times in a row is hard to fake.
- The result is **independent of where the code came from** — it's a property of
  the discretization on *this* problem, computed from the runs, not from
  anything the LLM claimed. That is the core "trustworthy, not just plausible"
  thesis of the talk.

**One sentence for the audience:** *"I imposed a known exact solution, refined
the grid four times, and measured how fast the error fell — it fell at exactly
the 2nd-order rate the central-difference scheme is designed for (p = 2.00 at
every refinement), which is concrete evidence the generated solver is correct,
not just plausible."*

## Nuance worth having ready

Because the Solov'ev profiles make the source linear in ψ, this is effectively a
linear elliptic solve, so SNES converges in a single Newton step. The agent
still selected SNES as the *general* Grad–Shafranov path (the same code handles
genuinely nonlinear `p(ψ)`, `F(ψ)` profiles unchanged); the linear manufactured
case is chosen for the verification test specifically because it is clean and
closed-form.

## Sources / reproduce

- Slide definition: `slides/make_slides.py` (slide 8, "Verification: it is actually right").
- Order computation: `src/verify_tokamak.py` (`orders()`, `main()`).
- Data: `figures/gs_verification.json`, `artifacts/run-20260723-113024/verification.json`.
- Q&A prep: `slides/PRESENTATION_QA.md` §2 "Verification & correctness".
- How to re-run the sweep: `docs/USAGE.md`, `docs/SESSION_LOG.md`.

---

## Milestone 9: verification of the shaped, real-machine equilibria

Session 5 extended the same MMS idea to **physically shaped, real-machine** equilibria by
swapping the toy `sin·sin` exact solution for the **Cerfon–Freidberg (2010) analytic Solov'ev
solution**. That solution is both a real tokamak equilibrium (D-shape / X-point set by ε, κ, δ)
*and* an exact closed-form answer, so the convergence test still applies — now on a physically
meaningful field. Three layers of verification:

1. **Symbolic (before any run).** `src/cerfon_freidberg.py` builds the solution with sympy and
   *proves* the identities `Δ*ψ_i ≡ 0` for every basis function and `Δ*ψ_p ≡ (1−A)x²+A`, and
   takes all boundary/curvature-constraint derivatives symbolically (no hand-differentiation).
   It then asserts ψ = 0 at the shaping points to machine precision, and — for the X-point case —
   that ∇ψ = 0 at the X-point (a genuine magnetic saddle, |∇ψ| ≈ 1.7×10⁻¹⁴).

2. **Convergence (the headline).** `src/verify_shaped.py` builds the *agent-generated* solver and
   runs the grid ladder against the CF analytic ψ. Observed order **p = 2.00, 2.00, 2.00** for
   **all three machines** (ITER limiter D-shape, NSTX-like spherical, and an X-point double-null),
   errors well above round-off. Same solver, correct on 1 and 4 MPI ranks (matching error).

3. **q-profile cross-check vs FreeGS** (`src/crosscheck_freegs.py`). Our contour-integral safety
   factor `q(ψ_N) = (1/2π)∮ F/(R|∇ψ|) dl` is checked against FreeGS's independent ray-traced
   `find_safety` **on the identical field** — agreement to **< 0.2%** for all three machines
   (a two-algorithm check of the integrator). A shape-matched FreeGS free-boundary run gives a
   physics "neighbour" comparison of κ, δ, q95 (e.g. X-point q95 = 3.19 vs FreeGS DIII-D 3.25).
   Measured κ, δ from the numerical flux surfaces match the *input* ε, κ, δ to ~1–2%.

**Why this is stronger than the toy case for the poster:** a bug in the shaped operator, the
nonzero Dirichlet boundary values (the plasma boundary ψ=0 is an *interior* contour here, not the
box edge), or the coefficient handling would break the 2.00 convergence — yet the agent-generated
solver hits it on three very different real-machine shapes with zero human edits to the solver.

Data: `artifacts/<run>/shaped/<machine>/verification.json`, `artifacts/<run>/shaped_summary.json`,
`artifacts/<run>/metrics.md`; figures `figures/shaped_{equilibria,convergence,qprofiles}.png`.

**Note on the X-point case:** it is an up-down **symmetric double-null** (X-points top and
bottom), built from the 7 even Cerfon–Freidberg basis functions with the high-point conditions
replaced by X-point saddle conditions (ψ = ψ_x = ψ_y = 0). This is a correct, fully-verified
X-point equilibrium; a *single-null* variant (the 12-coefficient asymmetric basis) is possible
future work.
