static char help[] =
  "Solve the tokamak Grad-Shafranov equilibrium for the poloidal flux psi(R,Z)\n"
  "on a 2D structured rectangular (R,Z) domain, verified via the method of\n"
  "manufactured solutions.\n\n"
  "Operator: Delta^* psi = d2psi/dR2 - (1/R) dpsi/dR + d2psi/dZ2\n"
  "Discretized with 2nd-order central finite differences on a PETSc DMDA and\n"
  "solved with SNES (linear residual, true Jacobian, converges in one Newton\n"
  "step).\n\n"
  "Options:\n"
  "  -da_grid_x <Nx>  number of grid points in R (default 65)\n"
  "  -da_grid_y <Nz>  number of grid points in Z (default 65)\n"
  "  -psi_view        VecView the numerical solution\n\n";

#include <petscsnes.h>
#include <petscdmda.h>

/* Problem geometry and manufactured-solution parameters, shared by the
   residual and Jacobian callbacks. */
typedef struct {
  PetscReal Rmin, Rmax;   /* R in [Rmin, Rmax]            */
  PetscReal Zmin, Zmax;   /* Z in [Zmin, Zmax]            */
  PetscReal aR, aZ;       /* manufactured wavenumbers     */
} AppCtx;

/* Manufactured exact solution: psi_exact(R,Z) = sin(aR (R-Rmin)) sin(aZ (Z-Zmin)).
   Vanishes on all four edges (homogeneous Dirichlet). */
static inline PetscReal PsiExact(AppCtx *u, PetscReal R, PetscReal Z)
{
  return PetscSinReal(u->aR * (R - u->Rmin)) * PetscSinReal(u->aZ * (Z - u->Zmin));
}

/* Exact Grad-Shafranov operator applied to psi_exact:
   Delta^* psi_exact =
     ( -aR^2 sin(aR(R-Rmin)) - (aR/R) cos(aR(R-Rmin)) ) sin(aZ(Z-Zmin))
     + sin(aR(R-Rmin)) ( -aZ^2 sin(aZ(Z-Zmin)) ).
   This is the manufactured right-hand side f(R,Z). */
static inline PetscReal ForcingF(AppCtx *u, PetscReal R, PetscReal Z)
{
  PetscReal sR = PetscSinReal(u->aR * (R - u->Rmin));
  PetscReal cR = PetscCosReal(u->aR * (R - u->Rmin));
  PetscReal sZ = PetscSinReal(u->aZ * (Z - u->Zmin));

  return (-u->aR * u->aR * sR - (u->aR / R) * cR) * sZ + sR * (-u->aZ * u->aZ * sZ);
}

/* Residual F(psi) = Delta^*_h psi - f, with Dirichlet rows F = psi - psi_exact. */
static PetscErrorCode FormFunction(SNES snes, Vec X, Vec Fvec, void *ctx)
{
  AppCtx        *user = (AppCtx *)ctx;
  DM             da;
  DMDALocalInfo  info;
  PetscReal      hR, hZ, R, Z;
  PetscScalar  **x, **f;
  Vec            Xloc;

  PetscFunctionBeginUser;
  PetscCall(SNESGetDM(snes, &da));
  PetscCall(DMDAGetLocalInfo(da, &info));

  hR = (user->Rmax - user->Rmin) / (PetscReal)(info.mx - 1);
  hZ = (user->Zmax - user->Zmin) / (PetscReal)(info.my - 1);

  /* Bring in ghost values for the current iterate. */
  PetscCall(DMGetLocalVector(da, &Xloc));
  PetscCall(DMGlobalToLocalBegin(da, X, INSERT_VALUES, Xloc));
  PetscCall(DMGlobalToLocalEnd(da, X, INSERT_VALUES, Xloc));

  PetscCall(DMDAVecGetArrayRead(da, Xloc, &x));
  PetscCall(DMDAVecGetArray(da, Fvec, &f));

  for (PetscInt j = info.ys; j < info.ys + info.ym; j++) {
    Z = user->Zmin + j * hZ;
    for (PetscInt i = info.xs; i < info.xs + info.xm; i++) {
      R = user->Rmin + i * hR;
      if (i == 0 || i == info.mx - 1 || j == 0 || j == info.my - 1) {
        /* Dirichlet boundary: psi = psi_exact (= 0 on all edges). */
        f[j][i] = x[j][i] - PsiExact(user, R, Z);
      } else {
        /* Delta^*_h psi = (psi_E - 2 psi_P + psi_W)/hR^2
                           - (1/R)(psi_E - psi_W)/(2 hR)
                           + (psi_N - 2 psi_P + psi_S)/hZ^2 */
        PetscScalar dRR = (x[j][i + 1] - 2.0 * x[j][i] + x[j][i - 1]) / (hR * hR);
        PetscScalar dR  = (x[j][i + 1] - x[j][i - 1]) / (2.0 * hR);
        PetscScalar dZZ = (x[j + 1][i] - 2.0 * x[j][i] + x[j - 1][i]) / (hZ * hZ);
        f[j][i] = dRR - dR / R + dZZ - ForcingF(user, R, Z);
      }
    }
  }

  PetscCall(DMDAVecRestoreArrayRead(da, Xloc, &x));
  PetscCall(DMDAVecRestoreArray(da, Fvec, &f));
  PetscCall(DMRestoreLocalVector(da, &Xloc));
  PetscFunctionReturn(PETSC_SUCCESS);
}

/* True Jacobian of the (linear) residual. */
static PetscErrorCode FormJacobian(SNES snes, Vec X, Mat J, Mat Jpre, void *ctx)
{
  AppCtx        *user = (AppCtx *)ctx;
  DM             da;
  DMDALocalInfo  info;
  PetscReal      hR, hZ, R;

  PetscFunctionBeginUser;
  PetscCall(SNESGetDM(snes, &da));
  PetscCall(DMDAGetLocalInfo(da, &info));

  hR = (user->Rmax - user->Rmin) / (PetscReal)(info.mx - 1);
  hZ = (user->Zmax - user->Zmin) / (PetscReal)(info.my - 1);

  for (PetscInt j = info.ys; j < info.ys + info.ym; j++) {
    for (PetscInt i = info.xs; i < info.xs + info.xm; i++) {
      MatStencil  row = {0}, col[5] = {{0}};
      PetscScalar v[5];
      PetscInt    n = 0;

      row.i = i;
      row.j = j;

      if (i == 0 || i == info.mx - 1 || j == 0 || j == info.my - 1) {
        /* Dirichlet row: identity. */
        col[0].i = i;
        col[0].j = j;
        v[0]     = 1.0;
        n        = 1;
      } else {
        R = user->Rmin + i * hR;

        /* South (j-1) */
        col[n].i = i;
        col[n].j = j - 1;
        v[n]     = 1.0 / (hZ * hZ);
        n++;
        /* West (i-1) */
        col[n].i = i - 1;
        col[n].j = j;
        v[n]     = 1.0 / (hR * hR) + 1.0 / (2.0 * hR * R);
        n++;
        /* Center */
        col[n].i = i;
        col[n].j = j;
        v[n]     = -2.0 / (hR * hR) - 2.0 / (hZ * hZ);
        n++;
        /* East (i+1) */
        col[n].i = i + 1;
        col[n].j = j;
        v[n]     = 1.0 / (hR * hR) - 1.0 / (2.0 * hR * R);
        n++;
        /* North (j+1) */
        col[n].i = i;
        col[n].j = j + 1;
        v[n]     = 1.0 / (hZ * hZ);
        n++;
      }
      PetscCall(MatSetValuesStencil(Jpre, 1, &row, n, col, v, INSERT_VALUES));
    }
  }

  PetscCall(MatAssemblyBegin(Jpre, MAT_FINAL_ASSEMBLY));
  PetscCall(MatAssemblyEnd(Jpre, MAT_FINAL_ASSEMBLY));
  if (J != Jpre) {
    PetscCall(MatAssemblyBegin(J, MAT_FINAL_ASSEMBLY));
    PetscCall(MatAssemblyEnd(J, MAT_FINAL_ASSEMBLY));
  }
  PetscFunctionReturn(PETSC_SUCCESS);
}

int main(int argc, char **argv)
{
  AppCtx             user;
  DM                 da;
  SNES               snes;
  Vec                x, r, xexact;
  Mat                J;
  DMDALocalInfo      info;
  PetscReal          hR, hZ, errinf, errl2;
  SNESConvergedReason reason;

  PetscFunctionBeginUser;
  PetscCall(PetscInitialize(&argc, &argv, NULL, help));

  /* Geometry and manufactured-solution parameters. */
  user.Rmin = 1.0;
  user.Rmax = 3.0;
  user.Zmin = -1.5;
  user.Zmax = 1.5;
  user.aR   = PETSC_PI / (user.Rmax - user.Rmin);
  user.aZ   = PETSC_PI / (user.Zmax - user.Zmin);

  /* Structured grid; default 65 x 65, override with -da_grid_x / -da_grid_y.
     Include the boundary points so hR=(Rmax-Rmin)/(Nx-1), hZ=(Zmax-Zmin)/(Nz-1). */
  PetscCall(DMDACreate2d(PETSC_COMM_WORLD, DM_BOUNDARY_NONE, DM_BOUNDARY_NONE,
                         DMDA_STENCIL_STAR, 65, 65, PETSC_DECIDE, PETSC_DECIDE,
                         1, 1, NULL, NULL, &da));
  PetscCall(DMSetFromOptions(da));
  PetscCall(DMSetUp(da));
  PetscCall(DMDASetUniformCoordinates(da, user.Rmin, user.Rmax, user.Zmin, user.Zmax, 0.0, 0.0));

  PetscCall(DMDAGetLocalInfo(da, &info));
  hR = (user.Rmax - user.Rmin) / (PetscReal)(info.mx - 1);
  hZ = (user.Zmax - user.Zmin) / (PetscReal)(info.my - 1);

  PetscCall(DMCreateGlobalVector(da, &x));
  PetscCall(VecDuplicate(x, &r));
  PetscCall(VecDuplicate(x, &xexact));
  PetscCall(DMCreateMatrix(da, &J));

  PetscCall(SNESCreate(PETSC_COMM_WORLD, &snes));
  PetscCall(SNESSetDM(snes, da));
  PetscCall(SNESSetFunction(snes, r, FormFunction, &user));
  PetscCall(SNESSetJacobian(snes, J, J, FormJacobian, &user));
  PetscCall(SNESSetFromOptions(snes));

  /* Solve Delta^* psi = f starting from zero. */
  PetscCall(VecSet(x, 0.0));
  PetscCall(SNESSolve(snes, NULL, x));
  PetscCall(SNESGetConvergedReason(snes, &reason));

  /* Build the exact solution on the grid. */
  {
    PetscScalar **xe;
    PetscCall(DMDAVecGetArray(da, xexact, &xe));
    for (PetscInt j = info.ys; j < info.ys + info.ym; j++) {
      PetscReal Z = user.Zmin + j * hZ;
      for (PetscInt i = info.xs; i < info.xs + info.xm; i++) {
        PetscReal R = user.Rmin + i * hR;
        xe[j][i] = PsiExact(&user, R, Z);
      }
    }
    PetscCall(DMDAVecRestoreArray(da, xexact, &xe));
  }

  /* Errors: max-norm and discrete L2 (h-weighted). */
  {
    Vec e;
    PetscReal nrm2;
    PetscCall(VecDuplicate(x, &e));
    PetscCall(VecWAXPY(e, -1.0, xexact, x)); /* e = x - xexact */
    PetscCall(VecNorm(e, NORM_INFINITY, &errinf));
    PetscCall(VecNorm(e, NORM_2, &nrm2));
    errl2 = nrm2 * PetscSqrtReal(hR * hZ);
    PetscCall(VecDestroy(&e));
  }

  /* Required output. */
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Grid Nx Nz            : %" PetscInt_FMT " %" PetscInt_FMT "\n", info.mx, info.my));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Spacings hR hZ        : %g %g\n", (double)hR, (double)hZ));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Max-norm error inf    : %g\n", (double)errinf));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Discrete L2 error     : %g\n", (double)errl2));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "SNESConvergedReason   : %s\n", SNESConvergedReasons[reason]));

  /* Optional: view the numerical solution. */
  {
    PetscBool view = PETSC_FALSE;
    PetscCall(PetscOptionsGetBool(NULL, NULL, "-psi_view", &view, NULL));
    if (view) PetscCall(VecView(x, PETSC_VIEWER_STDOUT_WORLD));
  }

  PetscCall(MatDestroy(&J));
  PetscCall(VecDestroy(&x));
  PetscCall(VecDestroy(&r));
  PetscCall(VecDestroy(&xexact));
  PetscCall(SNESDestroy(&snes));
  PetscCall(DMDestroy(&da));
  PetscCall(PetscFinalize());
  return 0;
}