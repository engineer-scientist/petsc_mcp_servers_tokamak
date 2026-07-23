#!/usr/bin/env python3
"""
orchestrate_tokamak.py -- project-owned orchestration driver for the PETSc
multi-agent tokamak-plasma simulation.

It drives the *real* specialist agents of gitlab.com/petsc/petsc_mcp_servers
(Mathematical Modeling -> Numerical Analysis -> HPC Code Generation -> compile/run)
for the tokamak Grad-Shafranov MHD-equilibrium problem, and captures every structured
intermediate artifact -- the proposal's "accumulated structured artifacts" and
"persistent decision-aware memory" -- under artifacts/<run-id>/ with full provenance.

The driver is:
  * faithful   -- it calls the shipped agent functions and the compile/run agent, using
                  the same claude_agent_sdk -> ANL Argo (Opus 4.8) backend;
  * verifiable -- code generation targets a manufactured/known-solution Grad-Shafranov
                  problem so the result can be checked (see verify_tokamak.py);
  * resumable  -- each stage writes a marker artifact; re-running skips completed stages
                  unless --force, so multi-session work continues cleanly.

Run (from anywhere) with the MCP-stack venv:
  env PYTHONPATH=/home/sarthak.sharma/petsc_mcp_servers \
      /home/sarthak.sharma/.venvs/mcp-test/bin/python \
      src/orchestrate_tokamak.py --stages model,na,codegen

See docs/ENVIRONMENT.md and docs/ARCHITECTURE.md.
"""
import os
import sys
import json
import time
import asyncio
import argparse
import datetime
import platform
import subprocess

# --- Locate the multi-agent system and force local stdio sub-server spawns ---------
MCP_DIR = os.environ.get("PETSC_MCP_DIR", "/home/sarthak.sharma/petsc_mcp_servers")
if MCP_DIR not in sys.path:
    sys.path.insert(0, MCP_DIR)
# Spawn any fan-out sub-servers (compile-run for the code generator) locally via stdio,
# using this interpreter (see the generateServer sys.executable patch). Must be set
# before importing the agent modules that read it.
os.environ.setdefault("PETSC_MCP_SERVERS_STDIO", "True")

import petscmcp  # noqa: E402  (auto-loads petsc_mcp_settings.json -> Argo key/model)
import pde_modeling_mcp_server as modeling_agent          # noqa: E402  Problem Definition
import na_mcp_server as na_agent                          # noqa: E402  Numerical Analysis
import petsc_claude_code_generator_mcp_server as codegen_agent  # noqa: E402  HPC Code Gen

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ARTIFACTS = os.path.join(PROJECT, "artifacts")

# ---------------------------------------------------------------------------------
# Problem specifications. The modeling/NA agents receive the *scientific* problem;
# the code generator receives a precise *engineering* spec chosen for a compiling,
# verifiable solver (structured grid + finite differences + SNES, manufactured
# Solov'ev-type solution -> exact convergence test, real flux-surface look).
# ---------------------------------------------------------------------------------
SCIENCE_SPEC = (
    "the Grad-Shafranov equilibrium for the magnetically confined plasma in a tokamak "
    "for nuclear fusion: the axisymmetric ideal-MHD force balance for the poloidal "
    "magnetic flux psi(R,Z) on a poloidal (R,Z) cross-section, "
    "Delta^* psi = -mu0 R^2 dp/dpsi - F dF/dpsi, with p(psi) the plasma pressure and "
    "F(psi)=R B_phi the poloidal current function, and a Dirichlet boundary psi=psi_b"
)

# Precise engineering spec for the HPC Code Generation agent. Prescriptive so the
# manufactured-solution verification is guaranteed to converge at 2nd order.
CODEGEN_SPEC = (
    "solves the tokamak Grad-Shafranov equilibrium for the poloidal magnetic flux "
    "psi(R,Z) on a 2D structured rectangular domain in the (R,Z) poloidal plane, and "
    "verifies itself with the method of manufactured solutions. "
    "Discretize the Grad-Shafranov operator "
    "Delta^* psi = d2psi/dR2 - (1/R) dpsi/dR + d2psi/dZ2 on a PETSc DMDA "
    "(DM_BOUNDARY_NONE, 1 dof, stencil width 1) using standard 2nd-order central "
    "finite differences, and solve with SNES (the residual is linear so Newton "
    "converges in one step; assemble the true Jacobian). "
    "Domain: R in [Rmin,Rmax] = [1.0, 3.0], Z in [Zmin,Zmax] = [-1.5, 1.5]; grid size "
    "from DMDA runtime options -da_grid_x and -da_grid_y (default 65 x 65); include the "
    "boundary points in the grid so the spacings are hR=(Rmax-Rmin)/(Nx-1), "
    "hZ=(Zmax-Zmin)/(Nz-1). "
    "Use the MANUFACTURED exact solution "
    "psi_exact(R,Z) = sin(aR*(R-Rmin)) * sin(aZ*(Z-Zmin)) with "
    "aR = PETSC_PI/(Rmax-Rmin) and aZ = PETSC_PI/(Zmax-Zmin), which vanishes on all four "
    "edges (homogeneous Dirichlet). Its exact Grad-Shafranov operator is "
    "Delta^* psi_exact = ( -aR*aR*sin(aR*(R-Rmin)) - (aR/R)*cos(aR*(R-Rmin)) )*sin(aZ*(Z-Zmin)) "
    "+ sin(aR*(R-Rmin))*( -aZ*aZ*sin(aZ*(Z-Zmin)) ). "
    "Set the right-hand side f(R,Z) = Delta^* psi_exact, impose the Dirichlet boundary "
    "condition psi = psi_exact (= 0) on all four edges, solve Delta^* psi = f, and "
    "compute the error against psi_exact. "
    "PRINT exactly these lines: the grid Nx Nz, the spacings hR hZ, the maximum-norm "
    "error ||psi_h - psi_exact||_inf, the discrete L2 error, and PETSc's "
    "SNESGetConvergedReason. Also support an option -psi_view to VecView the numerical "
    "solution. Make the code clean, use PetscCall() on every PETSc call, no %D formats, "
    "and be runnable on 1 or multiple MPI ranks."
)


def now_id():
    return "run-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def git_head(path):
    try:
        return subprocess.check_output(
            ["git", "-C", path, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unknown"


def write(path, data):
    with open(path, "w") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, indent=2))


def load_json(path):
    with open(path) as f:
        return json.load(f)


def load_manifest(outdir):
    p = os.path.join(outdir, "manifest.json")
    return load_json(p) if os.path.isfile(p) else {}


def save_manifest(outdir, m):
    write(os.path.join(outdir, "manifest.json"), m)


STAGE_MARKER = {"model": "model.json", "na": "na.json", "codegen": "grad_shafranov.c"}


def stage_done(outdir, name):
    m = load_manifest(outdir)
    if m.get("stages", {}).get(name, {}).get("status") == "ok":
        return True
    # Robustness: a written marker artifact also counts as done (crash after write,
    # before the manifest was updated) so resuming never re-spends an LLM call.
    marker = STAGE_MARKER.get(name)
    return bool(marker) and os.path.isfile(os.path.join(outdir, marker))


def record_stage(outdir, stage, status, **extra):
    m = load_manifest(outdir)
    m.setdefault("stages", {})[stage] = {"status": status,
                                         "at": datetime.datetime.now().isoformat(),
                                         **extra}
    save_manifest(outdir, m)


# ---------------------------------------------------------------------------------
# Stage 1 -- Mathematical Modeling agent (Problem Definition layer)
# ---------------------------------------------------------------------------------
async def stage_model(outdir):
    print("[model] Mathematical Modeling agent: generating PDE model ...", flush=True)
    t0 = time.time()
    r = await modeling_agent.generate_model_async(SCIENCE_SPEC)
    dt = time.time() - t0
    if "failure" in r or "failure_message" in r:
        record_stage(outdir, "model", "failed", seconds=round(dt, 1),
                     detail=r.get("failure") or r.get("failure_message"))
        raise RuntimeError("model stage failed: %s" % r)
    write(os.path.join(outdir, "model.json"),
          {k: r[k] for k in ("request", "name", "time-dependent") if k in r})
    if r.get("latex"):  write(os.path.join(outdir, "model.tex"), r["latex"])
    if r.get("html"):   write(os.path.join(outdir, "model.html"), r["html"])
    if r.get("python"): write(os.path.join(outdir, "model_ufl.py"), r["python"])
    if r.get("full-response"): write(os.path.join(outdir, "model_full.md"), r["full-response"])
    record_stage(outdir, "model", "ok", seconds=round(dt, 1),
                 name=r.get("name"), time_dependent=r.get("time-dependent"),
                 artifacts=["model.json", "model.tex", "model.html", "model_ufl.py"])
    print("[model] OK  name=%r  time-dependent=%s  (%.0fs)"
          % (r.get("name"), r.get("time-dependent"), dt), flush=True)
    return r


# ---------------------------------------------------------------------------------
# Stage 2 -- Numerical Analysis agent (Agent Execution layer)
# ---------------------------------------------------------------------------------
async def stage_na(outdir, model):
    print("[na] Numerical Analysis agent: selecting grid/discretization/solver ...", flush=True)
    t0 = time.time()
    # Feed the agent the scientific spec augmented with the model's key facts.
    na_spec = SCIENCE_SPEC + (
        ". The PDE is elliptic and %s. It is %s."
        % ("nonlinear (source depends on psi)",
           "time-dependent" if model.get("time-dependent") else "time-independent"))
    approach = await na_agent.select_approach_async(na_spec)
    dt = time.time() - t0
    if not isinstance(approach, dict) or "failure" in approach:
        record_stage(outdir, "na", "failed", seconds=round(dt, 1), detail=str(approach))
        raise RuntimeError("na stage failed: %s" % approach)
    grid = approach.get("grid")
    disc = approach.get("discretization")
    dm = na_agent.grid_and_discretization_to_petsc_dm(grid, disc) if grid and disc else None
    problem_class = "time-dependent" if model.get("time-dependent") else "nonlinear"
    solver = na_agent.petsc_solver(problem_class)
    out = {"select_approach": approach, "petsc_dm": dm,
           "problem_class": problem_class, "petsc_solver": solver}
    write(os.path.join(outdir, "na.json"), out)
    record_stage(outdir, "na", "ok", seconds=round(dt, 1),
                 grid=grid, discretization=disc, petsc_dm=dm, petsc_solver=solver,
                 artifacts=["na.json"])
    print("[na] OK  grid=%s disc=%s -> DM=%s ; class=%s -> solver=%s  (%.0fs)"
          % (grid, disc, dm, problem_class, solver, dt), flush=True)
    return out


# ---------------------------------------------------------------------------------
# Stage 3 -- HPC Code Generation agent (Agent Execution layer)
#            (generates + compiles + runs PETSc C via the compile-run agent)
# ---------------------------------------------------------------------------------
async def stage_codegen(outdir):
    print("[codegen] HPC Code Generation agent: generating + compiling PETSc C ...", flush=True)
    print("[codegen] (this drives an inner Claude with the compile-run tool; can take minutes)", flush=True)
    t0 = time.time()
    r = await codegen_agent.generate_code_async(CODEGEN_SPEC)
    dt = time.time() - t0
    write(os.path.join(outdir, "codegen.json"),
          {k: v for k, v in r.items() if k != "code"})
    if r.get("code"):
        write(os.path.join(outdir, "grad_shafranov.c"), r["code"])
    if r.get("output"):
        write(os.path.join(outdir, "codegen_output.txt"), str(r["output"]))
    ok = "code" in r and "failure_message" not in r
    record_stage(outdir, "codegen", "ok" if ok else "failed", seconds=round(dt, 1),
                 response_loops=r.get("response_loops"), tool_cnt=r.get("tool_cnt"),
                 failure_message=r.get("failure_message"),
                 artifacts=["grad_shafranov.c", "codegen.json", "codegen_output.txt"])
    status = "OK" if ok else "FAILED: %s" % r.get("failure_message")
    print("[codegen] %s  (loops=%s tools=%s, %.0fs)"
          % (status, r.get("response_loops"), r.get("tool_cnt"), dt), flush=True)
    if not ok:
        raise RuntimeError("codegen stage failed: %s" % r.get("failure_message"))
    return r


# ---------------------------------------------------------------------------------
def init_manifest(outdir, args):
    m = load_manifest(outdir)
    if not m:
        m = {
            "run_id": os.path.basename(outdir),
            "started": datetime.datetime.now().isoformat(),
            "host": platform.node(),
            "python": sys.version.split()[0],
            "model": petscmcp.defaultModel,
            "anthropic_base_url": os.environ.get("ANTHROPIC_BASE_URL"),
            "stages": {},
        }
    # Always refresh the provenance fields that reflect the *current* code/specs, so a
    # resumed run records the specs actually in force (not a stale copy from creation).
    m["mcp_servers_git"] = git_head(MCP_DIR)
    m["project_git"] = git_head(PROJECT)
    m["science_spec"] = SCIENCE_SPEC
    m["codegen_spec"] = CODEGEN_SPEC
    m["last_run"] = datetime.datetime.now().isoformat()
    save_manifest(outdir, m)
    return m


async def run(args):
    run_id = args.resume or now_id()
    outdir = os.path.join(ARTIFACTS, run_id)
    os.makedirs(outdir, exist_ok=True)
    init_manifest(outdir, args)
    print("=== tokamak orchestration  run_id=%s ===" % run_id, flush=True)
    print("    artifacts -> %s" % outdir, flush=True)
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]

    model = None
    if "model" in stages:
        if stage_done(outdir, "model") and not args.force:
            print("[model] cached, skipping (use --force to rerun)", flush=True)
            model = load_json(os.path.join(outdir, "model.json"))
        else:
            model = await stage_model(outdir)
    if model is None and os.path.isfile(os.path.join(outdir, "model.json")):
        model = load_json(os.path.join(outdir, "model.json"))

    if "na" in stages:
        if stage_done(outdir, "na") and not args.force:
            print("[na] cached, skipping (use --force to rerun)", flush=True)
        else:
            await stage_na(outdir, model or {})

    if "codegen" in stages:
        if stage_done(outdir, "codegen") and not args.force:
            print("[codegen] cached, skipping (use --force to rerun)", flush=True)
        else:
            await stage_codegen(outdir)

    m = load_manifest(outdir)
    m["finished"] = datetime.datetime.now().isoformat()
    save_manifest(outdir, m)
    print("=== done. stages: %s ==="
          % {k: v.get("status") for k, v in m.get("stages", {}).items()}, flush=True)
    print("    latest run: %s" % run_id, flush=True)
    # convenience pointer for the next session / verify step
    write(os.path.join(ARTIFACTS, "LATEST"), run_id + "\n")
    return outdir


def main():
    ap = argparse.ArgumentParser(description="Drive the PETSc multi-agent system for the tokamak GS problem.")
    ap.add_argument("--stages", default="model,na,codegen",
                    help="comma list of stages to run: model,na,codegen (default all)")
    ap.add_argument("--resume", default=None, metavar="RUN_ID",
                    help="resume/extend an existing artifacts/<RUN_ID> (skips completed stages)")
    ap.add_argument("--force", action="store_true", help="rerun stages even if cached")
    args = ap.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
