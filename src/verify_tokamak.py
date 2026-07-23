#!/usr/bin/env python3
"""
verify_tokamak.py -- verification + post-processing for the agent-generated
Grad-Shafranov solver.

This is the "verification-driven" half of the workflow (the proposal's first-class
validation step). It:
  1. builds the agent-generated PETSc C solver (artifacts/<run>/grad_shafranov.c),
  2. runs it on a ladder of grids (default 33,65,129,257) in the manufactured-solution
     mode, parsing the max-norm and L2 errors it prints,
  3. computes the observed order of accuracy p = log2(e_h / e_{h/2}) (expect ~2 for the
     2nd-order central-difference Grad-Shafranov operator),
  4. writes a convergence figure and a flux-surface figure (contours of the verified
     equilibrium psi) plus a JSON summary under figures/ and artifacts/<run>/.

Run with a Python that has numpy + matplotlib (e.g. /usr/bin/python3):
  PETSC_DIR=/home/sarthak.sharma/petsc PETSC_ARCH=arch-linux-c-opt \
    /usr/bin/python3 src/verify_tokamak.py            # uses artifacts/LATEST
  ... src/verify_tokamak.py --run run-YYYYmmdd-HHMMSS --sizes 33 65 129 257
"""
import os
import re
import sys
import json
import math
import shutil
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(PROJECT, "artifacts")
FIGURES = os.path.join(PROJECT, "figures")

PETSC_DIR = os.environ.get("PETSC_DIR", "/home/sarthak.sharma/petsc")
PETSC_ARCH = os.environ.get("PETSC_ARCH", "arch-linux-c-opt")

# Manufactured-solution / domain constants -- must match CODEGEN_SPEC in orchestrate_tokamak.py
RMIN, RMAX = 1.0, 3.0
ZMIN, ZMAX = -1.5, 1.5

FLOAT = r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?"


def latest_run():
    p = os.path.join(ARTIFACTS, "LATEST")
    if os.path.isfile(p):
        return open(p).read().strip()
    runs = sorted(d for d in os.listdir(ARTIFACTS)
                  if d.startswith("run-") and os.path.isdir(os.path.join(ARTIFACTS, d)))
    if not runs:
        sys.exit("no runs found in %s" % ARTIFACTS)
    return runs[-1]


def build(run_dir, workdir):
    src = os.path.join(run_dir, "grad_shafranov.c")
    if not os.path.isfile(src):
        sys.exit("generated solver not found: %s" % src)
    os.makedirs(workdir, exist_ok=True)
    shutil.copy(src, os.path.join(workdir, "grad_shafranov.c"))
    # Same recipe the compile-run agent uses: include PETSc's top-level conf and let
    # PETSC_ARCH (in the environment) select the build. Works for in-place PETSc trees.
    makefile = ("include ${PETSC_DIR}/lib/petsc/conf/variables\n"
                "include ${PETSC_DIR}/lib/petsc/conf/rules\n")
    with open(os.path.join(workdir, "makefile"), "w") as f:
        f.write(makefile)
    env = dict(os.environ, PETSC_DIR=PETSC_DIR, PETSC_ARCH=PETSC_ARCH)
    r = subprocess.run(["make", "grad_shafranov"], cwd=workdir, env=env,
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(os.path.join(workdir, "grad_shafranov")):
        print(r.stdout); print(r.stderr)
        sys.exit("build failed")
    print("[verify] built grad_shafranov")


def run_case(workdir, n):
    env = dict(os.environ, PETSC_DIR=PETSC_DIR, PETSC_ARCH=PETSC_ARCH)
    r = subprocess.run(["./grad_shafranov", "-da_grid_x", str(n), "-da_grid_y", str(n)],
                       cwd=workdir, env=env, capture_output=True, text=True, timeout=120)
    return r.stdout + "\n" + r.stderr


def parse_errors(out):
    """Tolerantly pull the max-norm and L2 errors from the solver's stdout."""
    maxerr = l2err = None
    for line in out.splitlines():
        low = line.lower()
        nums = re.findall(FLOAT, line)
        if not nums:
            continue
        val = float(nums[-1])
        if maxerr is None and (("max" in low and "norm" in low) or "inf" in low
                               or ("max" in low and "error" in low)):
            maxerr = val
        elif l2err is None and ("l2" in low or "l_2" in low or "2-norm" in low
                                or "two-norm" in low):
            l2err = val
    return maxerr, l2err


def orders(hs, errs):
    p = []
    for i in range(1, len(errs)):
        if errs[i] and errs[i - 1]:
            p.append(math.log(errs[i - 1] / errs[i]) / math.log(hs[i - 1] / hs[i]))
        else:
            p.append(float("nan"))
    return p


def make_figures(run_dir, sizes, hs, maxerrs, l2errs, ps):
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(FIGURES, exist_ok=True)

    # --- convergence figure ---
    fig, ax = plt.subplots(figsize=(6, 4.5))
    good = [(h, e) for h, e in zip(hs, maxerrs) if e]
    if good:
        hh, ee = zip(*good)
        ax.loglog(hh, ee, "o-", label=r"max-norm error $\|\psi_h-\psi_{\rm exact}\|_\infty$")
        if l2errs and any(l2errs):
            l2 = [(h, e) for h, e in zip(hs, l2errs) if e]
            if l2:
                hh2, ee2 = zip(*l2)
                ax.loglog(hh2, ee2, "s--", label=r"$L_2$ error")
        ref = [ee[0] * (h / hh[0]) ** 2 for h in hh]
        ax.loglog(hh, ref, "k:", label=r"2nd-order reference $\propto h^2$")
    ax.set_xlabel("grid spacing $h$")
    ax.set_ylabel("error")
    ax.set_title("Grad-Shafranov solver: manufactured-solution convergence")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURES, "gs_convergence.png"), dpi=150)
    plt.close(fig)

    # --- flux-surface figure (verified equilibrium: contours of psi_exact) ---
    aR = math.pi / (RMAX - RMIN)
    aZ = math.pi / (ZMAX - ZMIN)
    R = np.linspace(RMIN, RMAX, 400)
    Z = np.linspace(ZMIN, ZMAX, 400)
    RR, ZZ = np.meshgrid(R, Z)
    PSI = np.sin(aR * (RR - RMIN)) * np.sin(aZ * (ZZ - ZMIN))
    fig, ax = plt.subplots(figsize=(4.8, 5.6))
    cf = ax.contourf(RR, ZZ, PSI, levels=25, cmap="viridis")
    ax.contour(RR, ZZ, PSI, levels=12, colors="w", linewidths=0.6)
    ia, ja = np.unravel_index(np.argmax(PSI), PSI.shape)
    ax.plot(RR[ia, ja], ZZ[ia, ja], "r+", ms=12, mew=2, label="magnetic axis")
    ax.set_aspect("equal")
    ax.set_xlabel("R [m]"); ax.set_ylabel("Z [m]")
    ax.set_title("Poloidal flux surfaces $\\psi(R,Z)$\n(verified Grad-Shafranov solution)")
    ax.legend(fontsize=8, loc="upper right")
    fig.colorbar(cf, ax=ax, label=r"$\psi$", shrink=0.85)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURES, "gs_flux_surfaces.png"), dpi=150)
    plt.close(fig)
    # copy figures into the run dir too
    for f in ("gs_convergence.png", "gs_flux_surfaces.png"):
        shutil.copy(os.path.join(FIGURES, f), os.path.join(run_dir, f))
    print("[verify] wrote figures to %s" % FIGURES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--sizes", type=int, nargs="+", default=[33, 65, 129, 257])
    ap.add_argument("--show", action="store_true", help="print raw solver output for calibration")
    args = ap.parse_args()

    run_id = args.run or latest_run()
    run_dir = os.path.join(ARTIFACTS, run_id)
    workdir = os.path.join(PROJECT, "build", run_id)
    print("[verify] run=%s" % run_id)
    build(run_dir, workdir)

    sizes, hs, maxerrs, l2errs, raw = [], [], [], [], {}
    for n in args.sizes:
        out = run_case(workdir, n)
        raw[n] = out
        if args.show:
            print("----- N=%d -----\n%s" % (n, out))
        me, l2 = parse_errors(out)
        h = (RMAX - RMIN) / (n - 1)
        sizes.append(n); hs.append(h); maxerrs.append(me); l2errs.append(l2)
        print("[verify] N=%-4d h=%.4e  max-norm=%s  L2=%s" % (n, h, me, l2))

    ps = orders(hs, maxerrs)
    print("[verify] observed max-norm orders:", ["%.2f" % p for p in ps])

    summary = {"run": run_id, "sizes": sizes, "h": hs,
               "max_norm_error": maxerrs, "l2_error": l2errs,
               "observed_order_maxnorm": ps,
               "domain": {"R": [RMIN, RMAX], "Z": [ZMIN, ZMAX]}}
    with open(os.path.join(run_dir, "verification.json"), "w") as f:
        json.dump(summary, f, indent=2)
    os.makedirs(FIGURES, exist_ok=True)
    with open(os.path.join(FIGURES, "gs_verification.json"), "w") as f:
        json.dump(summary, f, indent=2)

    if any(maxerrs):
        make_figures(run_dir, sizes, hs, maxerrs, l2errs, ps)
    else:
        print("[verify] WARNING: no errors parsed; run with --show to calibrate parse_errors()")
    print("[verify] done. summary -> %s" % os.path.join(run_dir, "verification.json"))


if __name__ == "__main__":
    main()
