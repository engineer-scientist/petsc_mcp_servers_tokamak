static char help[] = "Grad-Shafranov axisymmetric tokamak equilibrium via PetscFE on a DMPLEX mesh.\n\n"
  "Solves the weak form   integral (1/R) grad(psi).grad(v) = integral (C1*R + C2/R) v,\n"
  "with homogeneous Dirichlet BC psi = 0 on the whole boundary of\n"
  "Omega = [R_in,R_out] x [Z_min,Z_max].  x[0]=R, x[1]=Z.\n\n";

#include <petscdmplex.h>
#include <petscsnes.h>
#include <petscds.h>
#include <petscfe.h>

/* Problem constants */
#define R_IN   0.5
#define R_OUT  1.5
#define Z_MIN (-1.0)
#define Z_MAX  1.0
#define C1     1.0
#define C2     1.0

/* Residual: f0(u,x) = -(C1*x[0] + C2/x[0])  (the source term, sign convention:
   residual = weak_laplacian - source). */
static void f0_gs(PetscInt dim, PetscInt Nf, PetscInt NfAux,
                  const PetscInt uOff[], const PetscInt uOff_x[], const PetscScalar u[], const PetscScalar u_t[], const PetscScalar u_x[],
                  const PetscInt aOff[], const PetscInt aOff_x[], const PetscScalar a[], const PetscScalar a_t[], const PetscScalar a_x[],
                  PetscReal t, const PetscReal x[], PetscInt numConstants, const PetscScalar constants[], PetscScalar f0[])
{
  const PetscReal R = x[0];
  f0[0] = -(C1 * R + C2 / R);
}

/* Residual: f1[d] = (1/R) * u_x[d]  (the weighted gradient term). */
static void f1_gs(PetscInt dim, PetscInt Nf, PetscInt NfAux,
                  const PetscInt uOff[], const PetscInt uOff_x[], const PetscScalar u[], const PetscScalar u_t[], const PetscScalar u_x[],
                  const PetscInt aOff[], const PetscInt aOff_x[], const PetscScalar a[], const PetscScalar a_t[], const PetscScalar a_x[],
                  PetscReal t, const PetscReal x[], PetscInt numConstants, const PetscScalar constants[], PetscScalar f1[])
{
  const PetscReal R = x[0];
  PetscInt        d;
  for (d = 0; d < dim; ++d) f1[d] = (1.0 / R) * u_x[d];
}

/* Jacobian: g3[d][d] = (1/R) on the diagonal (weighted Laplacian), zero off-diagonal. */
static void g3_gs(PetscInt dim, PetscInt Nf, PetscInt NfAux,
                  const PetscInt uOff[], const PetscInt uOff_x[], const PetscScalar u[], const PetscScalar u_t[], const PetscScalar u_x[],
                  const PetscInt aOff[], const PetscInt aOff_x[], const PetscScalar a[], const PetscScalar a_t[], const PetscScalar a_x[],
                  PetscReal t, PetscReal u_tShift, const PetscReal x[], PetscInt numConstants, const PetscScalar constants[], PetscScalar g3[])
{
  const PetscReal R = x[0];
  PetscInt        d;
  for (d = 0; d < dim; ++d) g3[d * dim + d] = 1.0 / R;
}

/* Homogeneous Dirichlet boundary value function: psi = 0. */
static PetscErrorCode zero_bc(PetscInt dim, PetscReal time, const PetscReal x[], PetscInt Nc, PetscScalar *u, void *ctx)
{
  PetscInt c;
  for (c = 0; c < Nc; ++c) u[c] = 0.0;
  return PETSC_SUCCESS;
}

static PetscErrorCode CreateMesh(MPI_Comm comm, DM *dm)
{
  PetscInt  cells[2]  = {16, 16};
  PetscReal lower[2]  = {R_IN, Z_MIN};
  PetscReal upper[2]  = {R_OUT, Z_MAX};

  PetscFunctionBeginUser;
  /* 2D simplex box mesh with interpolation and a "marker" label on the boundary faces. */
  PetscCall(DMPlexCreateBoxMesh(comm, 2, PETSC_TRUE, cells, lower, upper, NULL, PETSC_TRUE, 0, PETSC_FALSE, dm));
  PetscCall(PetscObjectSetName((PetscObject)*dm, "Tokamak cross-section"));
  PetscCall(DMSetFromOptions(*dm));
  PetscFunctionReturn(PETSC_SUCCESS);
}

static PetscErrorCode SetupProblem(DM dm)
{
  PetscDS        ds;
  DMLabel        label;
  const PetscInt id = 1; /* "marker" label value for boundary faces */

  PetscFunctionBeginUser;
  PetscCall(DMGetDS(dm, &ds));
  PetscCall(PetscDSSetResidual(ds, 0, f0_gs, f1_gs));
  PetscCall(PetscDSSetJacobian(ds, 0, 0, NULL, NULL, NULL, g3_gs));

  /* Homogeneous Dirichlet BC on the marked boundary. */
  PetscCall(DMGetLabel(dm, "marker", &label));
  PetscCall(PetscDSAddBoundary(ds, DM_BC_ESSENTIAL, "wall", label, 1, &id, 0, 0, NULL,
                               (void (*)(void))zero_bc, NULL, NULL, NULL));
  PetscFunctionReturn(PETSC_SUCCESS);
}

static PetscErrorCode SetupDiscretization(DM dm)
{
  DM             cdm = dm;
  PetscFE        fe;
  PetscInt       dim;
  PetscBool      simplex;

  PetscFunctionBeginUser;
  PetscCall(DMGetDimension(dm, &dim));
  PetscCall(DMPlexIsSimplex(dm, &simplex));
  /* Scalar (1 component) degree-1 Lagrange finite element for psi, matching the cell type. */
  PetscCall(PetscFECreateLagrange(PETSC_COMM_SELF, dim, 1, simplex, 1, PETSC_DETERMINE, &fe));
  PetscCall(PetscObjectSetName((PetscObject)fe, "psi"));
  PetscCall(DMSetField(dm, 0, NULL, (PetscObject)fe));
  PetscCall(DMCreateDS(dm));
  PetscCall(SetupProblem(dm));

  /* Propagate the discretization/BC info to any coarser DMs (needed for GAMG, harmless otherwise). */
  while (cdm) {
    PetscCall(DMCopyDisc(dm, cdm));
    PetscCall(DMGetCoarseDM(cdm, &cdm));
  }
  PetscCall(PetscFEDestroy(&fe));
  PetscFunctionReturn(PETSC_SUCCESS);
}

int main(int argc, char **argv)
{
  DM             dm;
  SNES           snes;
  Vec            psi;
  PetscReal      norm;
  PetscInt       ndof;

  PetscCall(PetscInitialize(&argc, &argv, NULL, help));

  /* Mesh */
  PetscCall(CreateMesh(PETSC_COMM_WORLD, &dm));

  /* Discretization + weak form + BC */
  PetscCall(SetupDiscretization(dm));

  /* Solver: SNES driving a linear FE problem via KSP. */
  PetscCall(SNESCreate(PETSC_COMM_WORLD, &snes));
  PetscCall(SNESSetDM(snes, dm));
  PetscCall(DMPlexSetSNESLocalFEM(dm, PETSC_FALSE, NULL));

  PetscCall(DMCreateGlobalVector(dm, &psi));
  PetscCall(PetscObjectSetName((PetscObject)psi, "psi"));
  PetscCall(VecSet(psi, 0.0)); /* zero initial guess */

  PetscCall(SNESSetFromOptions(snes));
  PetscCall(SNESSolve(snes, NULL, psi));

  /* Diagnostics */
  PetscCall(VecNorm(psi, NORM_2, &norm));
  PetscCall(VecGetSize(psi, &ndof));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Grad-Shafranov solve complete, ||psi||_2 = %g\n", (double)norm));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Number of degrees of freedom = %" PetscInt_FMT "\n", ndof));

  /* Cleanup */
  PetscCall(VecDestroy(&psi));
  PetscCall(SNESDestroy(&snes));
  PetscCall(DMDestroy(&dm));
  PetscCall(PetscFinalize());
  return 0;
}
