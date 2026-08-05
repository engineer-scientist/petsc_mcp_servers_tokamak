#!/usr/bin/env python3
"""
qprofile.py -- safety-factor q(psi_N) for a shaped Grad-Shafranov equilibrium.

The safety factor is the poloidal-flux-surface average

    q(psi) = (1 / 2 pi) * oint  F / (R^2 |grad psi|)  dl

around each closed flux surface, with F = R B_phi (the poloidal current function),
R the physical major radius, psi the physical poloidal flux, and dl the physical
poloidal arc length. It measures the field-line pitch and is THE headline profile of a
tokamak equilibrium (q on axis, q95 near the edge, and the shape in between).

This module is an INDEPENDENT implementation (contour extraction + closed-loop line
integral) -- deliberately a different algorithm from FreeGS's ray-traced `find_safety`,
so the milestone-9 cross-check (crosscheck_freegs.py, Technique A) is a genuine
apples-to-apples check of two different methods on the SAME field.

Works on either the analytic Cerfon-Freidberg field (from cerfon_freidberg.Case) or a
numerical psi grid (from the PETSc solver, in normalized x=R/R0 coordinates). Everything
is converted to PHYSICAL units (R0, psi0, F0 from the sidecar) before integrating.

Run with /usr/bin/python3 (numpy + scipy + matplotlib).
  /usr/bin/python3 src/qprofile.py --machine iter --plot
"""
import os
import json
import argparse

import numpy as np
from scipy.interpolate import RectBivariateSpline


class QInput:
    """Everything the q-integrator needs, in PHYSICAL units."""

    def __init__(self, R1d, Z1d, PSI, opoint, psi_axis, psi_bndry, F_of_psiN):
        # PSI has shape (len(R1d), len(Z1d)); PSI[i,j] = psi(R1d[i], Z1d[j]).
        self.R1d, self.Z1d, self.PSI = R1d, Z1d, PSI
        self.spline = RectBivariateSpline(R1d, Z1d, PSI)
        self.opoint = opoint                 # (R_axis, Z_axis)
        self.psi_axis = psi_axis             # physical psi on axis
        self.psi_bndry = psi_bndry           # physical psi on boundary
        self.F_of_psiN = F_of_psiN           # callable: psi_N -> F [T m]

    def psi(self, R, Z):
        return self.spline.ev(R, Z)

    def gradpsi(self, R, Z):
        return self.spline.ev(R, Z, dx=1, dy=0), self.spline.ev(R, Z, dx=0, dy=1)


# ---------------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------------
def from_analytic(case, n=500):
    """Build a QInput from an analytic cerfon_freidberg.Case (physical field)."""
    R0 = case.params["R0"]
    b = case.box
    R1d = np.linspace(b["xmin"], b["xmax"], n) * R0
    Z1d = np.linspace(b["ymin"], b["ymax"], n) * R0
    # PSI[i,j] = psi(R1d[i], Z1d[j]) -> use ij indexing.
    RR, ZZ = np.meshgrid(R1d, Z1d, indexing="ij")
    PSI = case.psi(RR, ZZ)                          # physical psi0 * psi_hat
    opoint = (R0 * case.opoint[0], R0 * case.opoint[1])
    psi_axis = case.psi0 * case.opoint[2]
    psi_bndry = 0.0

    def F_of_psiN(psiN):
        psi_phys = psi_axis + psiN * (psi_bndry - psi_axis)
        return case.F_of_psihat(psi_phys / case.psi0)

    return QInput(R1d, Z1d, PSI, opoint, psi_axis, psi_bndry, F_of_psiN)


def from_numerical(psi_hat, x1d, y1d, sidecar):
    """Build a QInput from a numerical psi_hat grid (normalized x,y) + a sidecar dict.

    psi_hat has shape (len(x1d), len(y1d)); psi_hat[i,j] = psi_hat(x1d[i], y1d[j])."""
    R0 = sidecar["R0"]; psi0 = sidecar["psi0"]; F0 = sidecar["F0"]; A = sidecar["A"]
    R1d = np.asarray(x1d) * R0
    Z1d = np.asarray(y1d) * R0
    PSI = psi0 * np.asarray(psi_hat)
    opoint = (R0 * sidecar["opoint"][0], R0 * sidecar["opoint"][1])
    psi_axis = psi0 * sidecar["opoint"][2]
    psi_bndry = 0.0

    def F_of_psiN(psiN):
        psi_phys = psi_axis + psiN * (psi_bndry - psi_axis)
        psi_hat_s = psi_phys / psi0
        F2 = F0**2 - 2.0 * A * (psi0**2 / R0**2) * psi_hat_s
        return np.sqrt(np.maximum(F2, 1e-30))

    return QInput(R1d, Z1d, PSI, opoint, psi_axis, psi_bndry, F_of_psiN)


# ---------------------------------------------------------------------------------
# Core: q on each flux surface
# ---------------------------------------------------------------------------------
def _closed_contour(R1d, Z1d, PSI, level, opoint):
    """Return (Rc, Zc) of the closed psi=level contour that encircles the axis, or None."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.path import Path

    RR, ZZ = np.meshgrid(R1d, Z1d, indexing="ij")
    fig = plt.figure()
    ax = fig.add_subplot(111)
    cs = ax.contour(RR, ZZ, PSI, levels=[level])
    segs = cs.allsegs[0] if cs.allsegs else []
    plt.close(fig)

    best = None
    for s in segs:
        if len(s) < 12:
            continue
        # close the loop if it very nearly closes
        seg = s if np.allclose(s[0], s[-1]) else np.vstack([s, s[0]])
        if Path(seg).contains_point(opoint) and (best is None or len(seg) > len(best)):
            best = seg
    if best is None:
        return None
    return best[:, 0], best[:, 1]


def _q_on_surface(qin, Rc, Zc, F_surf):
    """(1/2pi) oint F/(R |grad psi|) dl over the closed contour (Rc,Zc).

    q = (1/2pi) oint (B_phi/(R B_pol)) dl with B_phi=F/R and B_pol=|grad psi|/R, so the
    integrand is F/(R|grad psi|) (equivalently F/(R^2 B_pol), matching FreeGS)."""
    dR, dZ = qin.gradpsi(Rc, Zc)
    gmag = np.hypot(dR, dZ)
    integrand = F_surf / (Rc * gmag)
    dl = np.hypot(np.diff(Rc), np.diff(Zc))
    val = np.sum(0.5 * (integrand[:-1] + integrand[1:]) * dl)
    return val / (2.0 * np.pi)


def safety_factor(qin, psiN=None):
    """Return (psiN, q) arrays. Evaluate strictly on psi_N in (0,1) -- never at the axis
    (|grad psi| -> 0) or the separatrix (q -> inf for an X-point)."""
    if psiN is None:
        psiN = np.linspace(0.05, 0.95, 19)
    psiN = np.asarray(psiN, dtype=float)
    q = np.full(psiN.shape, np.nan)
    for k, pn in enumerate(psiN):
        level = qin.psi_axis + pn * (qin.psi_bndry - qin.psi_axis)
        cc = _closed_contour(qin.R1d, qin.Z1d, qin.PSI, level, qin.opoint)
        if cc is None:
            continue
        Rc, Zc = cc
        q[k] = abs(_q_on_surface(qin, Rc, Zc, float(qin.F_of_psiN(pn))))
    return psiN, q


def q0_q95(psiN, q):
    """Axis value (quadratic extrapolation to psi_N->0) and q95 (interpolated at 0.95)."""
    good = np.isfinite(q)
    pn, qq = psiN[good], q[good]
    if len(pn) < 3:
        return float("nan"), float("nan")
    # q0: quadratic fit on the innermost points
    m = min(5, len(pn))
    coef = np.polyfit(pn[:m], qq[:m], 2)
    q0 = float(np.polyval(coef, 0.0))
    q95 = float(np.interp(0.95, pn, qq))
    return q0, q95


# ---------------------------------------------------------------------------------
def plot_qprofile(psiN, q, title, path, dpi=150):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    q0, q95 = q0_q95(psiN, q)
    fig, ax = plt.subplots(figsize=(6, 4.5))
    good = np.isfinite(q)
    ax.plot(psiN[good], q[good], "o-", color="#0082CA", label="q(psi_N)")
    if np.isfinite(q0):
        ax.plot(0.0, q0, "s", color="#F8B200", label="q0 = %.2f (extrap.)" % q0)
    if np.isfinite(q95):
        ax.axvline(0.95, color="grey", ls=":", lw=1)
        ax.plot(0.95, q95, "^", color="crimson", label="q95 = %.2f" % q95)
    ax.set_xlabel(r"normalized flux $\psi_N$")
    ax.set_ylabel("safety factor q")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def main():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import cerfon_freidberg as cf

    ap = argparse.ArgumentParser(description="Safety-factor q(psi_N) for a CF equilibrium.")
    ap.add_argument("--machine", default="iter", choices=list(cf.MACHINES))
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    case = cf.solve_case(args.machine)
    qin = from_analytic(case)
    psiN, q = safety_factor(qin)
    q0, q95 = q0_q95(psiN, q)
    print("[q:%s] q0 = %.3f   q95 = %.3f" % (case.name, q0, q95))
    for pn, qq in zip(psiN, q):
        print("    psi_N=%.3f  q=%.4f" % (pn, qq))
    if args.plot:
        outdir = args.outdir or "."
        os.makedirs(outdir, exist_ok=True)
        p = plot_qprofile(psiN, q, "Safety factor: %s (analytic CF)" % case.name.upper(),
                          os.path.join(outdir, "qprofile_%s.png" % case.name))
        print("[q:%s] wrote %s" % (case.name, p))


if __name__ == "__main__":
    main()
