#!/usr/bin/env python3
"""
cerfon_freidberg.py -- analytic Cerfon-Freidberg (2010) Solov'ev Grad-Shafranov
equilibria: the "known answer" for milestone 9's shaped, real-machine verification.

Physics (all in NORMALIZED coordinates x = R/R0, y = Z/R0):

  Delta* psi = psi_xx - (1/x) psi_x + psi_yy = (1 - A) x^2 + A          (Solov'ev source)

The exact solution is  psi_hat(x,y) = psi_p + sum_i c_i psi_i, where psi_p is a
particular solution and psi_1..psi_12 are homogeneous solutions (Delta* psi_i = 0).
psi_1..psi_7 are even in y (up-down symmetric); psi_8..psi_12 are odd (needed for a
single-null X-point). The coefficients c_i are fixed by boundary + curvature constraints
on the Cerfon-Freidberg model surface

  x = 1 + eps cos(tau + alpha sin tau),   y = eps kappa sin tau,   alpha = arcsin(delta)

Because the source is linear, this is an EXACT closed-form GS equilibrium -- a rigorous
method-of-manufactured-solutions anchor (p ~ 2 convergence) whose field is nonetheless a
physically shaped, real-machine equilibrium (D-shape / X-point set by eps, kappa, delta).

sympy proves the basis identities exactly (Delta* psi_i == 0, Delta* psi_p == (1-A)x^2+A)
and takes every constraint derivative symbolically, so there is no hand-differentiation to
get wrong; a full-boundary psi ~ 0 assertion catches any bad constraint row.

Run with /usr/bin/python3 (needs numpy + sympy [+ matplotlib for --plot]).
NOTE: do NOT import this into the mcp-test driver venv -- it has no numpy. The driver only
runs the agent stages; this module (and verify_shaped/qprofile) run under /usr/bin/python3.

  /usr/bin/python3 src/cerfon_freidberg.py --machine iter --selfcheck --plot
"""
import os
import json
import argparse

import numpy as np
import sympy as sp

MU0 = 4.0e-7 * np.pi

# ---------------------------------------------------------------------------------
# Symbolic Cerfon-Freidberg construction (module-level: built once).
# ---------------------------------------------------------------------------------
_x, _y, _A = sp.symbols("x y A", real=True)
_LOG = sp.log


def _dstar(f):
    """Normalized Grad-Shafranov operator  Delta* f = f_xx - (1/x) f_x + f_yy."""
    return sp.diff(f, _x, 2) - sp.diff(f, _x) / _x + sp.diff(f, _y, 2)


# Particular solution: Delta* psi_p = (1 - A) x^2 + A.
_PSI_P = _x**4 / 8 + _A * ((_x**2 / 2) * _LOG(_x) - _x**4 / 8)

# Homogeneous basis. Index i-1 holds psi_i. 1..7 even in y; 8..12 odd in y (X-points).
_PSI = [
    sp.Integer(1),                                                              # psi_1
    _x**2,                                                                      # psi_2
    _y**2 - _x**2 * _LOG(_x),                                                   # psi_3
    _x**4 - 4 * _x**2 * _y**2,                                                  # psi_4
    2 * _y**4 - 9 * _y**2 * _x**2 + 3 * _x**4 * _LOG(_x)
        - 12 * _x**2 * _y**2 * _LOG(_x),                                        # psi_5
    _x**6 - 12 * _x**4 * _y**2 + 8 * _x**2 * _y**4,                             # psi_6
    (8 * _y**6 - 140 * _y**4 * _x**2 + 75 * _y**2 * _x**4 - 15 * _x**6 * _LOG(_x)
        + 180 * _x**4 * _y**2 * _LOG(_x) - 120 * _x**2 * _y**4 * _LOG(_x)),     # psi_7
    _y,                                                                         # psi_8
    _y * _x**2,                                                                 # psi_9
    _y**3 - 3 * _y * _x**2 * _LOG(_x),                                          # psi_10
    3 * _y * _x**4 - 4 * _y**3 * _x**2,                                         # psi_11
    (8 * _y**5 - 45 * _y * _x**4 - 80 * _y**3 * _x**2 * _LOG(_x)
        + 60 * _y * _x**4 * _LOG(_x)),                                         # psi_12
]


def verify_basis_identities():
    """Prove symbolically that Delta* psi_i == 0 for every basis function and that
    Delta* psi_p == (1-A) x^2 + A. Raises AssertionError on any mismatch."""
    for i, f in enumerate(_PSI, 1):
        r = sp.simplify(_dstar(f))
        assert r == 0, "Delta* psi_%d != 0 (got %s)" % (i, r)
    rp = sp.simplify(_dstar(_PSI_P) - ((1 - _A) * _x**2 + _A))
    assert rp == 0, "Delta* psi_p != (1-A)x^2 + A (got %s)" % rp


# ---------------------------------------------------------------------------------
# Machine registry. A is the Solov'ev free parameter (split of pressure vs current);
# R0 [m], B0 [T], Ip [A] set the physical scale (psi0 from Ip, F0 = R0 B0).
# ---------------------------------------------------------------------------------
MACHINES = {
    "iter": dict(eps=0.32, kappa=1.7, delta=0.33, A=-0.155,
                 R0=6.2, B0=5.3, Ip=15.0e6, kind="symmetric"),
    "nstx": dict(eps=0.78, kappa=2.0, delta=0.35, A=-0.05,
                 R0=0.85, B0=0.55, Ip=1.0e6, kind="symmetric"),
    "xpoint": dict(eps=0.32, kappa=1.7, delta=0.33, A=-0.155,
                   R0=6.2, B0=5.3, Ip=15.0e6, kind="xpoint"),
}


class Case:
    """A solved Cerfon-Freidberg equilibrium for one machine (all normalized fields in
    x=R/R0, y=Z/R0; psi0/F0 carry the physical scale)."""

    def __init__(self, name, p, c, box, psi_hat_fn, grad_fn, opoint, sep_point,
                 psi0, F0):
        self.name = name
        self.params = p
        self.c = c                       # length-12 coefficient vector (float)
        self.box = box                   # dict xmin,xmax,ymin,ymax (normalized)
        self._psi_hat = psi_hat_fn       # vectorized psi_hat(x,y)
        self._grad = grad_fn             # vectorized -> (dpsi/dx, dpsi/dy)
        self.opoint = opoint             # (x_axis, y_axis, psi_hat_axis)
        self.sep_point = sep_point       # (x, y, 0.0) boundary point (fake X-pt for q)
        self.psi0 = psi0                 # flux scale [Wb/rad], from Ip
        self.F0 = F0                     # R0 B0 [T m]

    # --- normalized field --------------------------------------------------------
    def psi_hat(self, x, y):
        return self._psi_hat(x, y)

    def grad_hat(self, x, y):
        return self._grad(x, y)

    # --- physical field ----------------------------------------------------------
    def psi(self, R, Z):
        R0 = self.params["R0"]
        return self.psi0 * self._psi_hat(R / R0, Z / R0)

    def F_of_psihat(self, psi_hat):
        """F(psi) for Solov'ev: F^2 = F0^2 - 2 A (psi0^2/R0^2)(psi_hat - psi_hat_bndry),
        with psi_hat_bndry = 0. Returns F [T m]."""
        A = self.params["A"]; R0 = self.params["R0"]
        F2 = self.F0**2 - 2.0 * A * (self.psi0**2 / R0**2) * psi_hat
        return np.sqrt(np.maximum(F2, 1e-30))

    def boundary_xy(self, tau):
        p = self.params
        eps, kappa, delta = p["eps"], p["kappa"], p["delta"]
        alpha = np.arcsin(delta)
        x = 1.0 + eps * np.cos(tau + alpha * np.sin(tau))
        y = eps * kappa * np.sin(tau)
        return x, y


def _lambdify(expr):
    return sp.lambdify((_x, _y), expr, modules="numpy")


def solve_case(name):
    """Solve for the coefficients c_i of machine `name` and return a Case."""
    if name not in MACHINES:
        raise KeyError("unknown machine %r (have %s)" % (name, list(MACHINES)))
    p = MACHINES[name]
    kind = p["kind"]
    if kind not in ("symmetric", "xpoint"):
        raise NotImplementedError("unknown kind %r for machine %r" % (kind, name))
    eps, kappa, delta, A = p["eps"], p["kappa"], p["delta"], p["A"]
    alpha = float(np.arcsin(delta))

    # Substitute the numeric A, then lambdify value + the derivatives the constraints
    # need, for the particular solution and the 7 even basis functions.
    subsA = {_A: A}
    psi_p = _PSI_P.subs(subsA)
    basis = [_PSI[i].subs(subsA) for i in range(7)]        # psi_1..psi_7

    def funcs(expr):
        return dict(
            val=_lambdify(expr),
            dx=_lambdify(sp.diff(expr, _x)),
            dxx=_lambdify(sp.diff(expr, _x, 2)),
            dy=_lambdify(sp.diff(expr, _y)),
            dyy=_lambdify(sp.diff(expr, _y, 2)),
        )

    fp = funcs(psi_p)
    fb = [funcs(b) for b in basis]

    # Constraint points and curvature coefficients (Cerfon-Freidberg eqs 8-10).
    xo, yo = 1.0 + eps, 0.0                 # outer equatorial
    xi, yi = 1.0 - eps, 0.0                 # inner equatorial
    xh, yh = 1.0 - delta * eps, kappa * eps  # high point
    N1 = -(1.0 + alpha) ** 2 / (eps * kappa**2)   # outer
    N2 = (1.0 - alpha) ** 2 / (eps * kappa**2)    # inner
    N3 = -kappa / (eps * np.cos(alpha) ** 2)      # high

    # Linear functionals L_k(f) applied to a basis function's callable-dict f. Both cases
    # use the 7 even (up-down symmetric) basis functions. "symmetric" is a limiter D-shape;
    # "xpoint" is an up-down symmetric DOUBLE-NULL where X-points at (x_sep, +/-y_sep) enter
    # as magnetic saddles (psi = psi_x = psi_y = 0), replacing the smooth high-point + high-
    # curvature conditions.
    def _cur_eq(f, x, y, N):                    # equatorial-point curvature condition
        return f["dyy"](x, y) + N * f["dx"](x, y)

    if kind == "symmetric":
        Ls = [
            lambda f: f["val"](xo, yo),                          # psi=0 outer
            lambda f: f["val"](xi, yi),                          # psi=0 inner
            lambda f: f["val"](xh, yh),                          # psi=0 high point
            lambda f: f["dx"](xh, yh),                           # psi_x=0 high (maximum)
            lambda f: _cur_eq(f, xo, yo, N1),                    # curvature outer
            lambda f: _cur_eq(f, xi, yi, N2),                    # curvature inner
            lambda f: f["dxx"](xh, yh) + N3 * f["dy"](xh, yh),   # curvature high
        ]
        sep_point = (xh, yh, 0.0)      # boundary high point (fake X-pt for FreeGS q)
        y_ext = kappa * eps
    else:  # kind == "xpoint": up-down symmetric double null
        xs = 1.0 - 1.1 * delta * eps
        ys = 1.1 * kappa * eps                                    # top X-point
        Ls = [
            lambda f: f["val"](xo, yo),                          # psi=0 outer
            lambda f: f["val"](xi, yi),                          # psi=0 inner
            lambda f: f["val"](xs, ys),                          # psi=0 at X-point
            lambda f: f["dx"](xs, ys),                           # psi_x=0 at X-point (Bz=0)
            lambda f: f["dy"](xs, ys),                           # psi_y=0 at X-point (Br=0)
            lambda f: _cur_eq(f, xo, yo, N1),                    # curvature outer
            lambda f: _cur_eq(f, xi, yi, N2),                    # curvature inner
        ]
        sep_point = (xs, ys, 0.0)      # true X-point
        y_ext = ys

    # M c = b, with M[k,j] = L_k(psi_j), b[k] = -L_k(psi_p).
    M = np.array([[Lk(fb[j]) for j in range(7)] for Lk in Ls], dtype=float)
    b = np.array([-Lk(fp) for Lk in Ls], dtype=float)
    c7 = np.linalg.solve(M, b)
    c = np.zeros(12)
    c[:7] = c7

    # Full symbolic solution -> vectorized psi_hat and its gradient.
    psi_sym = psi_p + sum(float(c7[j]) * basis[j] for j in range(7))
    psi_hat_fn = _lambdify(psi_sym)
    dpx = _lambdify(sp.diff(psi_sym, _x))
    dpy = _lambdify(sp.diff(psi_sym, _y))

    def grad_fn(x, y):
        return dpx(x, y), dpy(x, y)

    # MMS box: enclose the plasma (incl. X-points) with a 10% margin (left edge safely > 0).
    m = 0.10
    box = dict(xmin=1.0 - (1.0 + m) * eps, xmax=1.0 + (1.0 + m) * eps,
               ymin=-(1.0 + m) * y_ext, ymax=(1.0 + m) * y_ext)

    # Magnetic axis: on the midplane (y=0 by up-down symmetry) where psi_x = 0.
    x_ax = _find_axis(dpx, 1.0 - eps, 1.0 + eps)
    opoint = (x_ax, 0.0, float(psi_hat_fn(x_ax, 0.0)))

    # Flux scale from Ampere's law: mu0 Ip = (psi0/R0) * closed integral |grad psi_hat|/x dl_hat.
    psi0 = _psi0_from_Ip(p, dpx, dpy)
    F0 = p["R0"] * p["B0"]

    return Case(name, p, c, box, psi_hat_fn, grad_fn, opoint, sep_point, psi0, F0)


def _find_axis(dpsidx, xlo, xhi):
    """Locate the magnetic axis on y=0 as the root of psi_x(x,0) in [xlo,xhi]."""
    from scipy.optimize import brentq
    f = lambda x: float(dpsidx(x, 0.0))
    # scan for a sign change, then bracket-solve
    xs = np.linspace(xlo, xhi, 64)
    vals = [f(x) for x in xs]
    for k in range(len(xs) - 1):
        if vals[k] == 0.0:
            return float(xs[k])
        if vals[k] * vals[k + 1] < 0:
            return float(brentq(f, xs[k], xs[k + 1]))
    # fallback: extremum of |psi| on the midplane
    return float(xs[int(np.argmax(np.abs(vals)))])


def _psi0_from_Ip(p, dpsidx, dpsidy, n=4000):
    """psi0 [Wb/rad] such that the plasma current equals p['Ip'], from
    mu0 Ip = (psi0/R0) * oint |grad psi_hat| / x  dl_hat   over the boundary curve."""
    eps, kappa, delta = p["eps"], p["kappa"], p["delta"]
    alpha = np.arcsin(delta)
    tau = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    x = 1.0 + eps * np.cos(tau + alpha * np.sin(tau))
    y = eps * kappa * np.sin(tau)
    dxdt = -eps * np.sin(tau + alpha * np.sin(tau)) * (1.0 + alpha * np.cos(tau))
    dydt = eps * kappa * np.cos(tau)
    dl = np.sqrt(dxdt**2 + dydt**2)
    gmag = np.sqrt(dpsidx(x, y) ** 2 + dpsidy(x, y) ** 2)
    integral = np.trapz(gmag / x * dl, tau)          # oint |grad psi_hat|/x dl_hat
    return float(MU0 * p["Ip"] * p["R0"] / integral)


# ---------------------------------------------------------------------------------
# Self-checks
# ---------------------------------------------------------------------------------
def selfcheck(case, verbose=True):
    """Assert the equilibrium is exact: (a) basis identities (symbolic), (b) the solved
    solution satisfies Delta* psi_hat = (1-A)x^2+A symbolically, (c) psi_hat ~ 0 around
    the FULL model boundary (catches a bad constraint row)."""
    verify_basis_identities()

    # (b) end-to-end operator check with SYMBOLIC coefficients: proves that the assembled
    # solution psi_p + sum c_j psi_j satisfies Delta* psi_hat = (1-A)x^2+A for ANY c_j (it
    # follows from (a) by linearity; using symbols keeps it exact rather than round-off).
    A = case.params["A"]
    csym = sp.symbols("c1:13", real=True)
    psi_sym = _PSI_P + sum(csym[j] * _PSI[j] for j in range(12))
    resid = sp.simplify(_dstar(psi_sym) - ((1 - _A) * _x**2 + _A))
    assert resid == 0, "Delta* psi_hat != source (got %s)" % resid

    # ...and a numeric spot-check with the actual solved (float) coefficients.
    xs = np.array([0.85, 1.0, 1.12, 1.2]); ys = np.array([0.0, 0.2, -0.15, 0.3])
    lam_ds = _lambdify(_dstar(_PSI_P.subs({_A: A})
                              + sum(float(case.c[j]) * _PSI[j].subs({_A: A})
                                    for j in range(12))))
    got = lam_ds(xs, ys)
    want = (1 - A) * xs**2 + A
    op_err = float(np.max(np.abs(got - want)))
    assert op_err < 1e-10, "numeric operator residual too large: %.2e" % op_err

    # (c) boundary residual. The CF construction pins psi=0 EXACTLY at the 3 shaping
    # points (outer/inner/high) -- assert that to machine precision (catches a bad linear
    # solve). Around the FULL model curve psi=0 is only APPROXIMATE (the psi=0 contour is a
    # close fit to, not identical to, the parametric boundary): assert it stays small
    # relative to the axis amplitude, which catches a gross basis/constraint transcription
    # error (that would blow the fit up to O(1)).
    p = case.params
    kind = p["kind"]
    eps, kappa, delta = p["eps"], p["kappa"], p["delta"]
    if kind == "symmetric":
        pts = [(1 + eps, 0.0), (1 - eps, 0.0), (1 - delta * eps, kappa * eps)]
    else:  # xpoint: psi=0 imposed at outer, inner, and the X-point
        pts = [(1 + eps, 0.0), (1 - eps, 0.0), (case.sep_point[0], case.sep_point[1])]
    pt_res = float(max(abs(case.psi_hat(px, py)) for px, py in pts))

    # For the xpoint case the X-point is a saddle: grad psi = 0 there (a hard constraint).
    xpt_grad = None
    if kind == "xpoint":
        gx, gy = case.grad_hat(case.sep_point[0], case.sep_point[1])
        xpt_grad = float(np.hypot(gx, gy))

    # Model-curve fit is only meaningful for the smooth limiter boundary; for a diverted
    # (X-point) plasma the psi=0 separatrix departs from the smooth CF curve near the
    # X-point, so we report it but assert only in the symmetric case.
    tau = np.linspace(0.0, 2.0 * np.pi, 2000, endpoint=False)
    xb, yb = case.boundary_xy(tau)
    scale = max(abs(case.opoint[2]), 1e-300)      # interior amplitude (|psi| on axis)
    bmax = float(np.max(np.abs(case.psi_hat(xb, yb))))
    if verbose:
        print("[cf:%s] basis identities: OK (symbolic)" % case.name)
        print("[cf:%s] Delta* psi_hat == (1-A)x^2+A: OK (symbolic + numeric)" % case.name)
        print("[cf:%s] psi_hat at shaping/X points: max|psi| = %.2e (exact constraint)"
              % (case.name, pt_res))
        if xpt_grad is not None:
            print("[cf:%s] |grad psi_hat| at X-point = %.2e (saddle: must be 0)"
                  % (case.name, xpt_grad))
        print("[cf:%s] psi_hat around model curve: max|psi| = %.2e (rel = %.2e%s)"
              % (case.name, bmax, bmax / scale,
                 "" if kind == "symmetric" else "; not asserted for diverted plasma"))
        print("[cf:%s] coefficients c1..c7 = %s" % (
            case.name, ", ".join("%.6g" % v for v in case.c[:7])))
        print("[cf:%s] axis (x,psi_hat) = (%.5f, %.5e) ; psi0 = %.5e Wb/rad ; F0 = %.4f T m"
              % (case.name, case.opoint[0], case.opoint[2], case.psi0, case.F0))
    assert pt_res < 1e-9, "psi_hat not 0 at shaping/X points (%.2e): bad solve" % pt_res
    if kind == "xpoint":
        assert xpt_grad < 1e-9, "grad psi != 0 at X-point (%.2e): not a saddle" % xpt_grad
    else:
        assert bmax / scale < 5e-3, "boundary fit poor (rel %.2e): check basis" % (bmax / scale)
    return dict(shaping_point_res=pt_res, xpoint_grad=xpt_grad,
                boundary_rel=bmax / scale, boundary_abs=bmax)


# ---------------------------------------------------------------------------------
# Artifacts: PETSc options-file + sidecar JSON (+ optional flux-surface plot)
# ---------------------------------------------------------------------------------
def write_opts(case, path):
    """Write a PETSc options-file the agent-generated solver reads (coefficients as one
    real array; A, R0, and the normalized box)."""
    c = ",".join("%.17g" % v for v in case.c)
    lines = [
        "# Cerfon-Freidberg Solov'ev options for machine '%s' (normalized x=R/R0).\n" % case.name,
        "-cf_c %s\n" % c,
        "-cf_A %.17g\n" % case.params["A"],
        "-cf_R0 %.17g\n" % case.params["R0"],
        "-cf_xmin %.17g\n" % case.box["xmin"],
        "-cf_xmax %.17g\n" % case.box["xmax"],
        "-cf_ymin %.17g\n" % case.box["ymin"],
        "-cf_ymax %.17g\n" % case.box["ymax"],
    ]
    with open(path, "w") as f:
        f.writelines(lines)
    return path


def sidecar(case):
    p = case.params
    return {
        "machine": case.name,
        "kind": p["kind"],
        "eps": p["eps"], "kappa": p["kappa"], "delta": p["delta"], "A": p["A"],
        "R0": p["R0"], "B0": p["B0"], "Ip": p["Ip"],
        "box": case.box,
        "c": list(case.c),
        "opoint": list(case.opoint),
        "xpoint": list(case.sep_point),
        "psi0": case.psi0,
        "F0": case.F0,
        "psi_axis_phys": case.psi0 * case.opoint[2],
        "psi_bndry_phys": 0.0,
    }


def write_sidecar(case, path):
    with open(path, "w") as f:
        json.dump(sidecar(case), f, indent=2)
    return path


def plot_flux_surfaces(case, path, dpi=150):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    b = case.box
    R0 = case.params["R0"]
    xs = np.linspace(b["xmin"], b["xmax"], 400)
    ys = np.linspace(b["ymin"], b["ymax"], 500)
    XX, YY = np.meshgrid(xs, ys)
    PSI = case.psi_hat(XX, YY)

    fig, ax = plt.subplots(figsize=(5.0, 6.0))
    cf = ax.contourf(XX * R0, YY * R0, PSI, levels=30, cmap="viridis")
    ax.contour(XX * R0, YY * R0, PSI, levels=15, colors="w", linewidths=0.5)
    # separatrix / plasma boundary (psi_hat = 0) and the analytic model curve.
    ax.contour(XX * R0, YY * R0, PSI, levels=[0.0], colors="r", linewidths=1.8)
    tau = np.linspace(0, 2 * np.pi, 400)
    xb, yb = case.boundary_xy(tau)
    ax.plot(xb * R0, yb * R0, "r--", lw=1.0, label="model boundary")
    ax.plot(case.opoint[0] * R0, case.opoint[1] * R0, "w+", ms=12, mew=2,
            label="magnetic axis")
    if case.params["kind"] == "xpoint":
        xs, ys = case.sep_point[0] * R0, case.sep_point[1] * R0
        ax.plot([xs, xs], [ys, -ys], "rx", ms=11, mew=2.5, label="X-points")
    ax.set_aspect("equal")
    ax.set_xlabel("R [m]"); ax.set_ylabel("Z [m]")
    p = case.params
    ax.set_title("Cerfon-Freidberg Solov'ev equilibrium: %s\n"
                 "eps=%.2f kappa=%.2f delta=%.2f A=%.3f"
                 % (case.name.upper(), p["eps"], p["kappa"], p["delta"], p["A"]))
    ax.legend(fontsize=8, loc="upper right")
    fig.colorbar(cf, ax=ax, label=r"$\hat\psi$", shrink=0.85)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser(description="Analytic Cerfon-Freidberg Solov'ev equilibria.")
    ap.add_argument("--machine", default="iter", choices=list(MACHINES))
    ap.add_argument("--outdir", default=None,
                    help="write <machine>.opts + sidecar.json (+ plot) here")
    ap.add_argument("--selfcheck", action="store_true", help="run symbolic + boundary checks")
    ap.add_argument("--plot", action="store_true", help="write a flux-surface PNG")
    args = ap.parse_args()

    case = solve_case(args.machine)
    if args.selfcheck:
        selfcheck(case)
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        write_opts(case, os.path.join(args.outdir, "%s.opts" % case.name))
        write_sidecar(case, os.path.join(args.outdir, "sidecar.json"))
        print("[cf:%s] wrote %s.opts + sidecar.json -> %s"
              % (case.name, case.name, args.outdir))
        if args.plot:
            png = plot_flux_surfaces(case, os.path.join(args.outdir, "flux_surfaces.png"))
            print("[cf:%s] wrote %s" % (case.name, png))
    elif args.plot:
        png = plot_flux_surfaces(case, "cf_%s_flux_surfaces.png" % case.name)
        print("[cf:%s] wrote %s" % (case.name, png))


if __name__ == "__main__":
    main()
