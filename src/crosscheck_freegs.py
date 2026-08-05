#!/usr/bin/env python3
"""
crosscheck_freegs.py -- cross-check the shaped Cerfon-Freidberg equilibrium against the
FreeGS reference stack in ~/tokamak (milestone 9).

Two independent checks (FreeGS runs in ITS OWN venv via subprocess -- FreeGS 0.8.2 needs
numpy<2/scipy<1.14 and is never imported into this repo's interpreter):

  Technique A (method): feed OUR analytic CF field psi(R,Z) + F(psi) into FreeGS's own
    safety-factor routine (freegs.critical.find_safety, a ray-traced line integral) and
    compare its q(psi_N) to our qprofile.py result (a contour-based integral) on the
    IDENTICAL field. Two different algorithms on the same input -> validates our
    integrator. This is invariant to the flux scale psi0 and F (both sides see the same).

  Technique B (diagnostic): solve a shape-matched FreeGS FREE-boundary equilibrium
    (~/tokamak build_case + freegs.solve) and compare its scalar shape diagnostics
    (elongation kappa, triangularity delta, aspect ratio) and q95 to ours. This is a
    physics "neighbour" (FreeGS is coil-driven with placeholder profiles -- a different
    problem than our fixed-boundary analytic equilibrium), not a field match.

Run with /usr/bin/python3 (numpy/scipy; spawns ~/tokamak/.venv for FreeGS):
  /usr/bin/python3 src/crosscheck_freegs.py --machines iter
"""
import os
import sys
import json
import tempfile
import subprocess
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(PROJECT, "artifacts")
sys.path.insert(0, HERE)

import numpy as np                      # noqa: E402
import cerfon_freidberg as cf           # noqa: E402
import qprofile as qp                   # noqa: E402

FREEGS_PY = "/home/sarthak.sharma/tokamak/.venv/bin/python"
TOKAMAK_SRC = "/home/sarthak.sharma/tokamak/src"

# our-machine -> FreeGS machine registry key (see ~/tokamak/src/equilibrium.py MACHINES)
FREEGS_MACHINE = {"iter": "iterlike", "nstx": "mastu", "xpoint": "diiid"}


# ---------------------------------------------------------------------------------
# Technique A: FreeGS find_safety on OUR analytic field
# ---------------------------------------------------------------------------------
_FREEGS_Q_SCRIPT = r'''
import sys, json
import numpy as np
from scipy.interpolate import RectBivariateSpline
from freegs import critical

npz, out = sys.argv[1], sys.argv[2]
d = np.load(npz)
R1d, Z1d, PSI = d["R1d"], d["Z1d"], d["PSI"]
opoint = tuple(d["opoint"]); xpoint = tuple(d["xpoint"]); psiN = d["psiN"]
psi_axis = float(d["psi_axis"]); psi_bndry = float(d["psi_bndry"])
R0 = float(d["R0"]); psi0 = float(d["psi0"]); F0 = float(d["F0"]); A = float(d["A"])

spl = RectBivariateSpline(R1d, Z1d, PSI)
RR, ZZ = np.meshgrid(R1d, Z1d, indexing="ij")

class Duck:
    def __init__(self):
        self.R, self.Z = RR, ZZ
        self.Rmin, self.Rmax = float(R1d[0]), float(R1d[-1])
        self.Zmin, self.Zmax = float(Z1d[0]), float(Z1d[-1])
    def psi(self):
        return PSI
    def fpol(self, psinorm):
        psinorm = np.asarray(psinorm, dtype=float)
        psi_hat = (psi_axis + psinorm * (psi_bndry - psi_axis)) / psi0
        return np.sqrt(np.maximum(F0**2 - 2.0 * A * (psi0**2 / R0**2) * psi_hat, 1e-30))
    def Br(self, R, Z):
        return -spl.ev(R, Z, dx=0, dy=1) / R
    def Bz(self, R, Z):
        return spl.ev(R, Z, dx=1, dy=0) / R

q = critical.find_safety(Duck(), psinorm=psiN,
                         opoint=[opoint], xpoint=[xpoint])
json.dump({"psiN": list(map(float, psiN)),
           "q_freegs": [float(abs(v)) for v in np.atleast_1d(q)]},
          open(out, "w"))
'''


def technique_A(case, machine, outdir, n=256, psiN=None):
    if psiN is None:
        psiN = np.linspace(0.1, 0.9, 9)
    R0, psi0, F0, A = case.params["R0"], case.psi0, case.F0, case.params["A"]

    # physical field on a shared grid (used for BOTH integrators)
    b = case.box
    R1d = np.linspace(b["xmin"], b["xmax"], n) * R0
    Z1d = np.linspace(b["ymin"], b["ymax"], n) * R0
    RR, ZZ = np.meshgrid(R1d, Z1d, indexing="ij")
    PSI = case.psi(RR, ZZ)
    psi_axis = psi0 * case.opoint[2]
    psi_bndry = 0.0
    opoint = (R0 * case.opoint[0], R0 * case.opoint[1], psi_axis)
    xpoint = (R0 * case.sep_point[0], R0 * case.sep_point[1], psi_bndry)

    # our q on this exact grid
    def F_of_psiN(pn):
        psi_hat = (psi_axis + pn * (psi_bndry - psi_axis)) / psi0
        return np.sqrt(np.maximum(F0**2 - 2.0 * A * (psi0**2 / R0**2) * psi_hat, 1e-30))

    qin = qp.QInput(R1d, Z1d, PSI, (opoint[0], opoint[1]), psi_axis, psi_bndry, F_of_psiN)
    _, q_ours = qp.safety_factor(qin, psiN)

    # FreeGS q on the same field, via its own venv
    with tempfile.TemporaryDirectory() as td:
        npz = os.path.join(td, "field.npz")
        outj = os.path.join(td, "q.json")
        scr = os.path.join(td, "freegs_q.py")
        np.savez(npz, R1d=R1d, Z1d=Z1d, PSI=PSI, opoint=np.array(opoint),
                 xpoint=np.array(xpoint), psiN=psiN, psi_axis=psi_axis,
                 psi_bndry=psi_bndry, R0=R0, psi0=psi0, F0=F0, A=A)
        open(scr, "w").write(_FREEGS_Q_SCRIPT)
        r = subprocess.run([FREEGS_PY, scr, npz, outj], capture_output=True, text=True,
                           timeout=300)
        if not os.path.isfile(outj):
            return {"ok": False, "error": (r.stderr or r.stdout)[-800:]}
        fg = json.load(open(outj))

    q_fg = np.array(fg["q_freegs"], dtype=float)
    both = np.isfinite(q_ours) & np.isfinite(q_fg)
    rel = np.abs(q_ours[both] - q_fg[both]) / np.abs(q_fg[both])
    result = {
        "ok": bool(both.any() and np.max(rel) < 0.05),
        "psiN": list(map(float, psiN)),
        "q_ours": [None if v != v else float(v) for v in q_ours],
        "q_freegs": [None if v != v else float(v) for v in q_fg],
        "max_rel_diff": float(np.max(rel)) if both.any() else None,
        "mean_rel_diff": float(np.mean(rel)) if both.any() else None,
    }
    _plot_A(psiN, q_ours, q_fg, machine, os.path.join(outdir, "crosscheck_q.png"))
    print("[xcheck:%s] Technique A: q ours vs FreeGS find_safety, max rel diff = %s -> %s"
          % (machine, result["max_rel_diff"], result["ok"]))
    return result


# ---------------------------------------------------------------------------------
# Technique B: shape-matched FreeGS free-boundary equilibrium diagnostics
# ---------------------------------------------------------------------------------
_FREEGS_DIAG_SCRIPT = r'''
import sys, json
sys.path.insert(0, "%s")
import freegs
from equilibrium import build_case, diagnostics

machine, out = sys.argv[1], sys.argv[2]
tokamak, eq, profiles, control, xpoints, title = build_case(machine, 129, 129)
freegs.solve(eq, profiles, control)
d = diagnostics(eq)
json.dump({"machine_freegs": machine, "title": title, "diagnostics": d}, open(out, "w"))
''' % TOKAMAK_SRC


def technique_B(case, machine, outdir):
    fg_machine = FREEGS_MACHINE.get(machine)
    if fg_machine is None:
        return {"ok": None, "note": "no FreeGS machine mapped for %s" % machine}
    with tempfile.TemporaryDirectory() as td:
        outj = os.path.join(td, "diag.json")
        scr = os.path.join(td, "freegs_diag.py")
        open(scr, "w").write(_FREEGS_DIAG_SCRIPT)
        r = subprocess.run([FREEGS_PY, scr, fg_machine, outj], capture_output=True,
                           text=True, timeout=600)
        if not os.path.isfile(outj):
            return {"ok": False, "freegs_machine": fg_machine,
                    "error": (r.stderr or r.stdout)[-800:]}
        fg = json.load(open(outj))

    d = fg["diagnostics"]
    p = case.params
    # our measured shape (from the analytic separatrix) + q95
    qin = qp.from_analytic(case)
    from verify_shaped import measure_shape          # reuse the same measurement
    ours_shape = measure_shape(qin)
    psiN, q = qp.safety_factor(qin)
    _, ours_q95 = qp.q0_q95(psiN, q)
    result = {
        "ok": True,
        "freegs_machine": fg_machine,
        "input_shape": {"eps": p["eps"], "kappa": p["kappa"], "delta": p["delta"]},
        "compare": {
            "kappa":  {"ours": ours_shape.get("kappa_measured"), "freegs": d.get("elongation_kappa")},
            "delta":  {"ours": ours_shape.get("delta_measured"), "freegs": d.get("triangularity_delta")},
            "aspect": {"ours": ours_shape.get("aspect_ratio"),   "freegs": d.get("aspect_ratio_A")},
            "q95":    {"ours": ours_q95,                         "freegs": d.get("q95")},
        },
        "freegs_diagnostics": d,
    }
    print("[xcheck:%s] Technique B vs FreeGS %s: kappa %.2f/%.2f  delta %.2f/%.2f  q95 %.2f/%.2f"
          % (machine, fg_machine,
             result["compare"]["kappa"]["ours"] or float("nan"), d.get("elongation_kappa") or float("nan"),
             result["compare"]["delta"]["ours"] or float("nan"), d.get("triangularity_delta") or float("nan"),
             result["compare"]["q95"]["ours"] or float("nan"), d.get("q95") or float("nan")))
    return result


def _plot_A(psiN, q_ours, q_fg, machine, path, dpi=150):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.plot(psiN, q_ours, "o-", color="#0082CA", label="qprofile.py (contour integral)")
    ax.plot(psiN, q_fg, "s--", color="#F8B200", label="FreeGS find_safety (ray trace)")
    ax.set_xlabel(r"normalized flux $\psi_N$"); ax.set_ylabel("safety factor q")
    ax.set_title("q cross-check on the SAME analytic field: %s" % machine.upper())
    ax.grid(True, alpha=0.3); ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=dpi); plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--machines", nargs="+", default=["iter"])
    ap.add_argument("--run", default=None, help="write results under artifacts/<run>/shaped/<m>/")
    args = ap.parse_args()

    out = {}
    for machine in args.machines:
        case = cf.solve_case(machine)
        if args.run:
            outdir = os.path.join(ARTIFACTS, args.run, "shaped", machine)
        else:
            outdir = os.path.join("/tmp", "xcheck_%s" % machine)
        os.makedirs(outdir, exist_ok=True)
        A = technique_A(case, machine, outdir)
        B = technique_B(case, machine, outdir)
        res = {"technique_A": A, "technique_B": B}
        json.dump(res, open(os.path.join(outdir, "crosscheck.json"), "w"), indent=2)
        out[machine] = res
        print("[xcheck:%s] wrote %s" % (machine, os.path.join(outdir, "crosscheck.json")))
    return out


if __name__ == "__main__":
    main()
