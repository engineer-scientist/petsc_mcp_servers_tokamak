#!/usr/bin/env python3
"""
make_shaped_figures.py -- combined poster/slide figures for milestone 9 (shaped, real-machine
Cerfon-Freidberg equilibria), aggregated across machines from a shaped verification run.

Writes to figures/:
  shaped_equilibria.png   -- 3-panel flux surfaces (ITER / NSTX / X-point), separatrix + O/X
  shaped_convergence.png  -- all machines' manufactured-solution convergence on one log-log axis
  shaped_qprofiles.png    -- all machines' safety-factor q(psi_N) on one axis

Reads the per-machine artifacts/<run>/shaped/<machine>/verification.json for the measured
convergence + q data; re-solves the analytic case for the flux-surface panels.

Run with /usr/bin/python3 (numpy + scipy + matplotlib):
  /usr/bin/python3 src/make_shaped_figures.py --run run-YYYYmmdd-HHMMSS --machines iter nstx xpoint
"""
import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(PROJECT, "artifacts")
FIGURES = os.path.join(PROJECT, "figures")
sys.path.insert(0, HERE)

import numpy as np                      # noqa: E402
import matplotlib                       # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt         # noqa: E402
import cerfon_freidberg as cf           # noqa: E402

COLORS = {"iter": "#0082CA", "nstx": "#E4572E", "xpoint": "#6A4C93"}


def _latest_shaped():
    p = os.path.join(ARTIFACTS, "LATEST")
    if os.path.isfile(p):
        rid = open(p).read().strip()
        m = os.path.join(ARTIFACTS, rid, "manifest.json")
        if os.path.isfile(m) and json.load(open(m)).get("problem") == "shaped":
            return rid
    runs = [d for d in sorted(os.listdir(ARTIFACTS)) if d.startswith("run-")]
    for rid in reversed(runs):
        m = os.path.join(ARTIFACTS, rid, "manifest.json")
        if os.path.isfile(m) and json.load(open(m)).get("problem") == "shaped":
            return rid
    sys.exit("no shaped run found")


def flux_panel(machines, path, dpi=150):
    # Each equilibrium is a tall-narrow, equal-aspect (R,Z) plot; size each column to its own
    # width/height ratio so the panels pack tightly with no wasted horizontal space.
    cases = [cf.solve_case(m) for m in machines]
    aspects = []
    for case in cases:
        R0 = case.params["R0"]; b = case.box
        aspects.append(((b["xmax"] - b["xmin"]) * R0) / ((b["ymax"] - b["ymin"]) * R0))
    panel_h = 4.6
    fig_w = panel_h * sum(aspects) + 0.9        # + y-label / inter-panel spacing
    fig_h = panel_h + 0.7                        # + suptitle / x-labels
    fig, axes = plt.subplots(1, len(machines), figsize=(fig_w, fig_h),
                             gridspec_kw={"width_ratios": aspects}, constrained_layout=True)
    if len(machines) == 1:
        axes = [axes]
    for ax, case, machine in zip(axes, cases, machines):
        R0 = case.params["R0"]; b = case.box
        xs = np.linspace(b["xmin"], b["xmax"], 400)
        ys = np.linspace(b["ymin"], b["ymax"], 500)
        XX, YY = np.meshgrid(xs, ys)
        PSI = case.psi_hat(XX, YY)
        ax.contourf(XX * R0, YY * R0, PSI, levels=30, cmap="viridis")
        ax.contour(XX * R0, YY * R0, PSI, levels=14, colors="w", linewidths=0.4)
        ax.contour(XX * R0, YY * R0, PSI, levels=[0.0], colors="r", linewidths=1.8)
        ax.plot(case.opoint[0] * R0, 0.0, "w+", ms=11, mew=2)
        if case.params["kind"] == "xpoint":
            xsx, ysx = case.sep_point[0] * R0, case.sep_point[1] * R0
            ax.plot([xsx, xsx], [ysx, -ysx], "rx", ms=10, mew=2.2)
        ax.set_aspect("equal")
        ax.margins(0)
        ax.set_xlabel("R [m]")
        p = case.params
        ax.set_title("%s\n$\\epsilon$=%.2f $\\kappa$=%.1f $\\delta$=%.2f"
                     % (machine.upper(), p["eps"], p["kappa"], p["delta"]), fontsize=10)
    axes[0].set_ylabel("Z [m]")
    fig.suptitle("Agent-generated shaped Grad-Shafranov equilibria (Cerfon-Freidberg Solov'ev)",
                 fontsize=12)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def convergence_panel(run_id, machines, path, dpi=150):
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    hmin = 1e9
    for machine in machines:
        v = json.load(open(os.path.join(ARTIFACTS, run_id, "shaped", machine,
                                        "verification.json")))
        hs = v["h"]; me = v["max_norm_error"]
        pts = [(h, e) for h, e in zip(hs, me) if e]
        hh, ee = zip(*pts)
        hmin = min(hmin, min(hh))
        order = ", ".join("%.2f" % p for p in v["observed_order_maxnorm"] if p == p)
        ax.loglog(hh, ee, "o-", color=COLORS.get(machine, None),
                  label="%s  (p = %s)" % (machine.upper(), order))
    # single 2nd-order reference line
    xr = np.array([hmin, max(hh)])
    ax.loglog(xr, ee[0] * (xr / hh[0]) ** 2, "k:", lw=1.2, label=r"$\propto h^2$")
    ax.set_xlabel("normalized grid spacing $h$")
    ax.set_ylabel(r"max-norm error $\|\psi_h-\psi_{\rm CF}\|_\infty$")
    ax.set_title("Shaped Grad-Shafranov: 2nd-order convergence vs. analytic solution",
                 fontsize=11)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def qprofile_panel(run_id, machines, path, dpi=150):
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    for machine in machines:
        v = json.load(open(os.path.join(ARTIFACTS, run_id, "shaped", machine,
                                        "verification.json")))
        q = v["qprofile"]
        pn = np.array(q["psiN"], float)
        qq = np.array([np.nan if x is None else x for x in q["q"]], float)
        good = np.isfinite(qq)
        ax.plot(pn[good], qq[good], "o-", color=COLORS.get(machine, None),
                label="%s  (q95 = %.2f)" % (machine.upper(), q["q95"]))
    ax.set_xlabel(r"normalized flux $\psi_N$")
    ax.set_ylabel("safety factor q")
    ax.set_title("Safety-factor profiles of the verified shaped equilibria")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--machines", nargs="+", default=["iter", "nstx", "xpoint"])
    args = ap.parse_args()
    run_id = args.run or _latest_shaped()
    os.makedirs(FIGURES, exist_ok=True)
    print("[figs] run=%s machines=%s" % (run_id, args.machines))
    print("[figs] wrote", flux_panel(args.machines, os.path.join(FIGURES, "shaped_equilibria.png")))
    print("[figs] wrote", convergence_panel(run_id, args.machines,
                                            os.path.join(FIGURES, "shaped_convergence.png")))
    print("[figs] wrote", qprofile_panel(run_id, args.machines,
                                         os.path.join(FIGURES, "shaped_qprofiles.png")))


if __name__ == "__main__":
    main()
