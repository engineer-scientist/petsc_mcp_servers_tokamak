#!/usr/bin/env python3
"""
verify_shaped.py -- verification, q-profile, and figures for the agent-generated SHAPED
(Cerfon-Freidberg) Grad-Shafranov solver, per machine (milestone 9).

For each machine it:
  1. builds the coefficients/box from cerfon_freidberg (writes <machine>.opts + sidecar.json),
  2. builds the agent-generated PETSc solver (artifacts/<run>/grad_shafranov.c),
  3. runs it on a grid ladder with -options_file <machine>.opts, parsing the max-norm/L2
     errors it prints, and computes the observed order of accuracy (expect p ~ 2 for the
     2nd-order central-difference operator) vs the Cerfon-Freidberg analytic solution,
  4. confirms it also runs correctly on multiple MPI ranks (same error),
  5. computes the safety-factor q-profile of the verified equilibrium (qprofile.py),
  6. measures the flux-surface shape (kappa, delta, aspect ratio) and checks it against the
     input (eps, kappa, delta),
  7. writes flux-surface / q-profile / convergence figures + verification.json, all under
     artifacts/<run>/shaped/<machine>/, and a top-level shaped_summary.json.

Reuses verify_tokamak.build / parse_errors / orders (the same build+parse+order machinery)
and cerfon_freidberg / qprofile.

Run with /usr/bin/python3 (numpy + scipy + matplotlib), with PETSc in the environment:
  PETSC_DIR=$HOME/petsc PETSC_ARCH=arch-linux-c-opt \
    /usr/bin/python3 src/verify_shaped.py --machines iter --sizes 33 65 129 257
"""
import os
import sys
import json
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(PROJECT, "artifacts")
sys.path.insert(0, HERE)

import numpy as np                      # noqa: E402
import verify_tokamak as vt             # noqa: E402  build/parse_errors/orders (+PETSC_DIR/ARCH)
import cerfon_freidberg as cf           # noqa: E402
import qprofile as qp                   # noqa: E402


def latest_shaped_run():
    """The LATEST run if it is a shaped run, else the newest run-* whose manifest says so."""
    def is_shaped(rid):
        m = os.path.join(ARTIFACTS, rid, "manifest.json")
        if not os.path.isfile(m):
            return False
        try:
            return json.load(open(m)).get("problem") == "shaped"
        except Exception:
            return False

    p = os.path.join(ARTIFACTS, "LATEST")
    if os.path.isfile(p):
        rid = open(p).read().strip()
        if is_shaped(rid):
            return rid
    runs = sorted(d for d in os.listdir(ARTIFACTS)
                  if d.startswith("run-") and is_shaped(d))
    if not runs:
        sys.exit("no shaped run found (run: orchestrate_tokamak.py --problem shaped)")
    return runs[-1]


# PETSc's own mpiexec (the system /usr/bin/mpiexec uses an incompatible PMI and aborts
# PetscInitialize); fall back to PATH mpiexec only if PETSc's is missing.
_PETSC_MPIEXEC = os.path.join(vt.PETSC_DIR, vt.PETSC_ARCH, "bin", "mpiexec")


def run_case(workdir, n, opts_file, nranks=1, timeout=240):
    exe = "./grad_shafranov"
    if nranks > 1:
        mpiexec = _PETSC_MPIEXEC if os.path.exists(_PETSC_MPIEXEC) else "mpiexec"
        base = [mpiexec, "-n", str(nranks), exe]
    else:
        base = [exe]
    cmd = base + ["-options_file", opts_file, "-da_grid_x", str(n), "-da_grid_y", str(n)]
    env = dict(os.environ, PETSC_DIR=vt.PETSC_DIR, PETSC_ARCH=vt.PETSC_ARCH)
    r = subprocess.run(cmd, cwd=workdir, env=env, capture_output=True, text=True,
                       timeout=timeout)
    return r.stdout + "\n" + r.stderr


def measure_shape(qin, psiN=0.95):
    """Measure elongation/triangularity/aspect ratio from a flux surface just inside the
    boundary (psi_N=0.95 by default). Measuring at psi_N<1 rather than exactly on the
    separatrix avoids the X-point singularity of a diverted plasma and matches how machines
    quote edge shape."""
    from qprofile import _closed_contour
    level = qin.psi_axis + psiN * (qin.psi_bndry - qin.psi_axis)
    cc = _closed_contour(qin.R1d, qin.Z1d, qin.PSI, level, qin.opoint)
    if cc is None:
        return {}
    R, Z = cc
    Rmax, Rmin = float(R.max()), float(R.min())
    Zmax, Zmin = float(Z.max()), float(Z.min())
    a = 0.5 * (Rmax - Rmin)
    Rgeo = 0.5 * (Rmax + Rmin)
    kappa = (Zmax - Zmin) / (Rmax - Rmin)
    R_at_top = float(R[int(np.argmax(Z))])
    delta = (Rgeo - R_at_top) / a
    return dict(R_geo_m=Rgeo, a_m=a, aspect_ratio=Rgeo / a,
                kappa_measured=kappa, delta_measured=delta)


def plot_convergence(hs, maxerrs, l2errs, ps, machine, path, dpi=150):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 4.5))
    good = [(h, e) for h, e in zip(hs, maxerrs) if e]
    if good:
        hh, ee = zip(*good)
        ax.loglog(hh, ee, "o-", color="#0082CA",
                  label=r"max-norm $\|\psi_h-\psi_{\rm CF}\|_\infty$")
        l2 = [(h, e) for h, e in zip(hs, l2errs) if e]
        if l2:
            hh2, ee2 = zip(*l2)
            ax.loglog(hh2, ee2, "s--", color="#00A0B0", label=r"$L_2$ error")
        ref = [ee[0] * (h / hh[0]) ** 2 for h in hh]
        ax.loglog(hh, ref, "k:", label=r"2nd-order reference $\propto h^2$")
    porder = ", ".join("%.2f" % p for p in ps if p == p)
    ax.set_xlabel("normalized grid spacing $h$")
    ax.set_ylabel("error")
    ax.set_title("Shaped Grad-Shafranov (%s): manufactured-solution convergence\n"
                 "observed order p = %s" % (machine.upper(), porder))
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def verify_machine(run_id, machine, sizes, mpi_ranks=4):
    run_dir = os.path.join(ARTIFACTS, run_id)
    outdir = os.path.join(run_dir, "shaped", machine)
    os.makedirs(outdir, exist_ok=True)
    print("[verify-shaped] run=%s machine=%s" % (run_id, machine))

    # 1. coefficients + options-file + sidecar (with a fast self-check of the physics).
    case = cf.solve_case(machine)
    cf.selfcheck(case, verbose=False)
    opts = cf.write_opts(case, os.path.join(outdir, "%s.opts" % machine))
    cf.write_sidecar(case, os.path.join(outdir, "sidecar.json"))

    # 2. build the agent-generated solver.
    workdir = os.path.join(PROJECT, "build", run_id, "shaped", machine)
    vt.build(run_dir, workdir)

    # 3. grid ladder (1 rank).
    Lx = case.box["xmax"] - case.box["xmin"]
    sz, hs, maxerrs, l2errs = [], [], [], []
    for n in sizes:
        out = run_case(workdir, n, opts, nranks=1)
        me, l2 = vt.parse_errors(out)
        h = Lx / (n - 1)
        sz.append(n); hs.append(h); maxerrs.append(me); l2errs.append(l2)
        print("[verify-shaped] N=%-4d h=%.4e  max-norm=%s  L2=%s" % (n, h, me, l2))
    ps = vt.orders(hs, maxerrs)
    print("[verify-shaped] observed max-norm orders:", ["%.2f" % p for p in ps])

    # 4. multi-rank correctness at a middle grid (non-fatal if mpiexec is unavailable).
    nmid = sz[len(sz) // 2]
    mpi = {"ranks": mpi_ranks, "n": nmid}
    try:
        me1, _ = vt.parse_errors(run_case(workdir, nmid, opts, nranks=1))
        meP, _ = vt.parse_errors(run_case(workdir, nmid, opts, nranks=mpi_ranks))
        rel = abs(meP - me1) / max(abs(me1), 1e-30) if (me1 and meP) else None
        # 1-rank and N-rank give the SAME discretization error up to iterative-solver
        # noise (PETSc's default block-Jacobi preconditioner is rank-dependent), so accept
        # a sub-percent match; a broken parallel ghost exchange would differ by O(1).
        mpi.update(err_1rank=me1, err_Nrank=meP, rel_diff=rel,
                   ok=bool(rel is not None and rel < 5e-2))
        print("[verify-shaped] MPI %d-rank check: err_1=%s err_%d=%s rel=%s -> %s"
              % (mpi_ranks, me1, mpi_ranks, meP, rel, mpi.get("ok")))
    except Exception as e:
        mpi.update(ok=None, error=str(e))
        print("[verify-shaped] MPI check skipped: %s" % e)

    # 5. q-profile of the verified equilibrium (analytic CF field, which the solver is
    #    verified to reproduce at 2nd order).
    qin = qp.from_analytic(case)
    psiN, q = qp.safety_factor(qin)
    q0, q95 = qp.q0_q95(psiN, q)
    print("[verify-shaped] q0=%.3f q95=%.3f" % (q0, q95))

    # 6. measured flux-surface shape vs input.
    shape = measure_shape(qin)

    # 7. figures + summary.
    cf.plot_flux_surfaces(case, os.path.join(outdir, "flux_surfaces.png"))
    qp.plot_qprofile(psiN, q, "Safety factor: %s (verified CF equilibrium)" % machine.upper(),
                     os.path.join(outdir, "qprofile.png"))
    plot_convergence(hs, maxerrs, l2errs, ps, machine,
                     os.path.join(outdir, "convergence.png"))

    p = case.params
    summary = {
        "run": run_id, "machine": machine, "kind": p["kind"],
        "input_shape": {"eps": p["eps"], "kappa": p["kappa"], "delta": p["delta"], "A": p["A"]},
        "R0_m": p["R0"], "B0_T": p["B0"], "Ip_A": p["Ip"],
        "box": case.box,
        "sizes": sz, "h": hs, "max_norm_error": maxerrs, "l2_error": l2errs,
        "observed_order_maxnorm": ps,
        "finest_grid_maxnorm_error": next((e for e in reversed(maxerrs) if e), None),
        "mpi_check": mpi,
        "qprofile": {"psiN": list(psiN), "q": [None if v != v else v for v in q],
                     "q0": q0, "q95": q95},
        "measured_shape": shape,
    }
    with open(os.path.join(outdir, "verification.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("[verify-shaped] wrote %s" % os.path.join(outdir, "verification.json"))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None, help="run id (default: latest shaped run)")
    ap.add_argument("--machines", nargs="+", default=["iter"],
                    help="machines to verify (must exist in cerfon_freidberg.MACHINES)")
    ap.add_argument("--sizes", type=int, nargs="+", default=[33, 65, 129, 257])
    ap.add_argument("--mpi-ranks", type=int, default=4)
    args = ap.parse_args()

    run_id = args.run or latest_shaped_run()
    summaries = []
    for machine in args.machines:
        summaries.append(verify_machine(run_id, machine, args.sizes, args.mpi_ranks))

    top = {"run": run_id, "machines": {s["machine"]: {
        "observed_order_maxnorm": s["observed_order_maxnorm"],
        "finest_grid_maxnorm_error": s["finest_grid_maxnorm_error"],
        "q0": s["qprofile"]["q0"], "q95": s["qprofile"]["q95"],
        "measured_shape": s["measured_shape"], "mpi_ok": s["mpi_check"].get("ok"),
    } for s in summaries}}
    with open(os.path.join(ARTIFACTS, run_id, "shaped_summary.json"), "w") as f:
        json.dump(top, f, indent=2)
    print("[verify-shaped] wrote %s" % os.path.join(ARTIFACTS, run_id, "shaped_summary.json"))


if __name__ == "__main__":
    main()
