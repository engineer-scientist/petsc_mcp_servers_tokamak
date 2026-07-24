static char help[] =
    "Grad-Shafranov equilibrium (Solov'ev linear source) solved with PetscFE.\n"
    "Solves:  R d/dR((1/R) dpsi/dR) + d^2psi/dZ^2 = -(C1*R^2 + C2)\n"
    "Weak form: int (1/R) grad(psi).grad(v) = int (C1*R + C2/R) v\n"
    "Domain: [0.5,1.5] x [-1.0,1.0], homogeneous Dirichlet BC.\n\n";

#include <petscdmplex.h>
#include <petscsnes.h>
#include <petscfe.h>
#include <petscds.h>

/* Physics constants */
static const PetscReal C1 = 1.0;
static const PetscReal C2 = 1.0;

/* Domain bounds (R = x[0], Z = x[1]) */
static const PetscReal Rlo = 0.5, Rhi = 1.5;
static const PetscReal Zlo = -1.0, Zhi = 1.0;

/* ---- Pointwise weak-form callbacks ----
   Residual:  int ( v * f0 + grad(v) . f1 ) dx = 0
   We want:   int (1/R) grad(psi).grad(v) - int (C1*R + C2/R) v = 0
*/

/* f0 = -(C1*R + C2/R)  (the source term, moved to the residual) */
static void f0_gs(PetscInt dim, PetscInt Nf, PetscInt NfAux,
                  const PetscInt uOff[], const PetscInt uOff_x[], const PetscScalar u[],
                  const PetscScalar u_t[], const PetscScalar u_x[],
                  const PetscInt aOff[], const PetscInt aOff_x[], const PetscScalar a[],
                  const PetscScalar a_t[], const PetscScalar a_x[],
                  PetscReal t, const PetscReal x[], PetscInt numConstants,
                  const PetscScalar constants[], PetscScalar f0[])
{
  const PetscReal R = x[0];
  f0[0] = -(C1 * R + C2 / R);
}

/* f1[d] = (1/R) * grad(psi)[d] */
static void f1_gs(PetscInt dim, PetscInt Nf, PetscInt NfAux,
                  const PetscInt uOff[], const PetscInt uOff_x[], const PetscScalar u[],
                  const PetscScalar u_t[], const PetscScalar u_x[],
                  const PetscInt aOff[], const PetscInt aOff_x[], const PetscScalar a[],
                  const PetscScalar a_t[], const PetscScalar a_x[],
                  PetscReal t, const PetscReal x[], PetscInt numConstants,
                  const PetscScalar constants[], PetscScalar f1[])
{
  const PetscReal R = x[0];
  PetscInt        d;
  for (d = 0; d < dim; ++d) f1[d] = u_x[d] / R;
}

/* Jacobian: g3[d][e] = (1/R) delta_{d,e} */
static void g3_gs(PetscInt dim, PetscInt Nf, PetscInt NfAux,
                  const PetscInt uOff[], const PetscInt uOff_x[], const PetscScalar u[],
                  const PetscScalar u_t[], const PetscScalar u_x[],
                  const PetscInt aOff[], const PetscInt aOff_x[], const PetscScalar a[],
                  const PetscScalar a_t[], const PetscScalar a_x[],
                  PetscReal t, PetscReal u_tShift, const PetscReal x[],
                  PetscInt numConstants, const PetscScalar constants[], PetscScalar g3[])
{
  const PetscReal R = x[0];
  PetscInt        d;
  for (d = 0; d < dim; ++d) g3[d * dim + d] = 1.0 / R;
}

/* Essential (Dirichlet) boundary value: psi = 0 */
static PetscErrorCode zero_bc(PetscInt dim, PetscReal time, const PetscReal x[],
                              PetscInt Nc, PetscScalar *u, void *ctx)
{
  PetscInt c;
  for (c = 0; c < Nc; ++c) u[c] = 0.0;
  return PETSC_SUCCESS;
}

/* Create the DMPLEX box mesh over the physical (R,Z) domain */
static PetscErrorCode CreateMesh(MPI_Comm comm, DM *dm)
{
  DM             pdm = NULL;
  PetscInt       dim = 2;
  PetscInt       faces[2] = {10, 20};
  PetscReal      lower[2] = {Rlo, Zlo};
  PetscReal      upper[2] = {Rhi, Zhi};
  DMBoundaryType periodicity[2] = {DM_BOUNDARY_NONE, DM_BOUNDARY_NONE};

  PetscFunctionBeginUser;
  /* Structured simplex box mesh mapped directly onto [Rlo,Rhi] x [Zlo,Zhi] */
  PetscCall(DMPlexCreateBoxMesh(comm, dim, PETSC_TRUE, faces, lower, upper, periodicity, PETSC_TRUE, 0, PETSC_TRUE, dm));
  /* Allow command-line refinement / customization */
  PetscCall(DMSetFromOptions(*dm));
  /* Distribute if run in parallel */
  PetscCall(DMPlexDistribute(*dm, 0, NULL, &pdm));
  if (pdm) {
    PetscCall(DMDestroy(dm));
    *dm = pdm;
  }
  PetscCall(DMSetApplicationContext(*dm, NULL));
  PetscCall(PetscObjectSetName((PetscObject)*dm, "Grad-Shafranov mesh"));
  PetscCall(DMViewFromOptions(*dm, NULL, "-dm_view"));
  PetscFunctionReturn(PETSC_SUCCESS);
}

/* Set up the PetscFE discretization and the discrete system (PetscDS) */
static PetscErrorCode SetupDiscretization(DM dm)
{
  PetscFE        fe;
  PetscDS        ds;
  DMLabel        label;
  PetscInt       dim;
  const PetscInt id = 1; /* "marker" boundary label value for box mesh */

  PetscFunctionBeginUser;
  PetscCall(DMGetDimension(dm, &dim));
  /* Continuous Lagrange element, scalar field, order chosen via -psi_petscspace_degree */
  PetscCall(PetscFECreateDefault(PETSC_COMM_SELF, dim, 1, PETSC_TRUE, "psi_", -1, &fe));
  PetscCall(PetscObjectSetName((PetscObject)fe, "psi"));
  PetscCall(DMSetField(dm, 0, NULL, (PetscObject)fe));
  PetscCall(DMCreateDS(dm));

  PetscCall(DMGetDS(dm, &ds));
  PetscCall(PetscDSSetResidual(ds, 0, f0_gs, f1_gs));
  PetscCall(PetscDSSetJacobian(ds, 0, 0, NULL, NULL, NULL, g3_gs));

  /* Homogeneous Dirichlet BC on all boundary faces (label "marker", value 1) */
  PetscCall(DMGetLabel(dm, "marker", &label));
  PetscCall(DMAddBoundary(dm, DM_BC_ESSENTIAL, "wall", label, 1, &id, 0, 0, NULL,
                          (void (*)(void))zero_bc, NULL, NULL, NULL));

  PetscCall(PetscFEDestroy(&fe));
  PetscFunctionReturn(PETSC_SUCCESS);
}

int main(int argc, char **argv)
{
  DM             dm;
  SNES           snes;
  KSP            ksp;
  Vec            u;
  PetscInt       gdof, its;
  PetscReal      nrm2, nrmInf;
  SNESConvergedReason reason;
  KSPConvergedReason  kreason;

  PetscCall(PetscInitialize(&argc, &argv, NULL, help));

  /* Mesh + discretization */
  PetscCall(CreateMesh(PETSC_COMM_WORLD, &dm));
  PetscCall(SetupDiscretization(dm));

  /* Solution vector */
  PetscCall(DMCreateGlobalVector(dm, &u));
  PetscCall(PetscObjectSetName((PetscObject)u, "psi"));
  PetscCall(VecSet(u, 0.0)); /* zero initial guess */

  /* SNES driving a linear FE problem (converges in one Newton step) */
  PetscCall(SNESCreate(PETSC_COMM_WORLD, &snes));
  PetscCall(SNESSetDM(snes, dm));
  PetscCall(DMPlexSetSNESLocalFEM(dm, PETSC_FALSE, NULL));
  PetscCall(SNESSetFromOptions(snes));

  PetscCall(SNESSolve(snes, NULL, u));

  /* Convergence diagnostics */
  PetscCall(SNESGetConvergedReason(snes, &reason));
  PetscCall(SNESGetIterationNumber(snes, &its));
  PetscCall(SNESGetKSP(snes, &ksp));
  PetscCall(KSPGetConvergedReason(ksp, &kreason));

  /* Degrees of freedom */
  PetscCall(VecGetSize(u, &gdof));

  /* Solution norms */
  PetscCall(VecNorm(u, NORM_2, &nrm2));
  PetscCall(VecNorm(u, NORM_INFINITY, &nrmInf));

  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "=== Grad-Shafranov (Solov'ev) FE solve ===\n"));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Domain: R in [%g,%g], Z in [%g,%g]\n",
                        (double)Rlo, (double)Rhi, (double)Zlo, (double)Zhi));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Constants: C1 = %g, C2 = %g\n", (double)C1, (double)C2));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Global degrees of freedom: %d\n", (int)gdof));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "SNES converged reason: %s (Newton its = %d)\n",
                        SNESConvergedReasons[reason], (int)its));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "KSP  converged reason: %s\n",
                        KSPConvergedReasons[kreason]));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "||psi||_2   = %.10e\n", (double)nrm2));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "||psi||_inf = %.10e\n", (double)nrmInf));
  if (reason > 0) {
    PetscCall(PetscPrintf(PETSC_COMM_WORLD, "RESULT: SOLVE CONVERGED SUCCESSFULLY\n"));
  } else {
    PetscCall(PetscPrintf(PETSC_COMM_WORLD, "RESULT: SOLVE DID NOT CONVERGE\n"));
  }

  PetscCall(VecViewFromOptions(u, NULL, "-sol_view"));

  /* Cleanup */
  PetscCall(VecDestroy(&u));
  PetscCall(SNESDestroy(&snes));
  PetscCall(DMDestroy(&dm));
  PetscCall(PetscFinalize());
  return 0;
}
