static char help[] =
    "Tokamak Grad-Shafranov Solov'ev equilibrium (Cerfon-Freidberg) in\n"
    "normalized coordinates x=R/R0, y=Z/R0, verified by the method of\n"
    "manufactured solutions on a DMDA using SNES.\n\n"
    "Delta^* psi = d2psi/dx2 - (1/x) dpsi/dx + d2psi/dy2 = f,   f=(1-A)x^2+A\n\n"
    "Options:\n"
    "  -cf_xmin -cf_xmax -cf_ymin -cf_ymax : rectangular box (normalized)\n"
    "  -cf_A                               : Solov'ev scalar A\n"
    "  -cf_c                               : 12 basis coefficients (array)\n"
    "  -da_grid_x -da_grid_y               : grid size (incl. boundary pts)\n"
    "  -psi_view                           : VecView the numerical solution\n\n";

#include <petscsnes.h>
#include <petscdm.h>
#include <petscdmda.h>

typedef struct {
  PetscReal xmin, xmax, ymin, ymax; /* normalized computational box */
  PetscReal A;                      /* Solov'ev scalar               */
  PetscReal c[12];                  /* homogeneous basis coefficients */
} AppCtx;

/* Manufactured exact Cerfon-Freidberg flux PsiExact(x,y). */
static PetscReal PsiExact(const AppCtx *u, PetscReal x, PetscReal y)
{
  PetscReal        L  = PetscLogReal(x);
  PetscReal        x2 = x * x, x4 = x2 * x2, x6 = x4 * x2;
  PetscReal        y2 = y * y, y3 = y2 * y, y4 = y2 * y2, y5 = y4 * y, y6 = y4 * y2;
  PetscReal        A  = u->A;
  const PetscReal *c  = u->c;
  PetscReal        psip, p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12;

  psip = x4 / 8.0 + A * ((x2 / 2.0) * L - x4 / 8.0);

  p1  = 1.0;
  p2  = x2;
  p3  = y2 - x2 * L;
  p4  = x4 - 4.0 * x2 * y2;
  p5  = 2.0 * y4 - 9.0 * y2 * x2 + 3.0 * x4 * L - 12.0 * x2 * y2 * L;
  p6  = x6 - 12.0 * x4 * y2 + 8.0 * x2 * y4;
  p7  = 8.0 * y6 - 140.0 * y4 * x2 + 75.0 * y2 * x4 - 15.0 * x6 * L + 180.0 * x4 * y2 * L - 120.0 * x2 * y4 * L;
  p8  = y;
  p9  = y * x2;
  p10 = y3 - 3.0 * y * x2 * L;
  p11 = 3.0 * y * x4 - 4.0 * y3 * x2;
  p12 = 8.0 * y5 - 45.0 * y * x4 - 80.0 * y3 * x2 * L + 60.0 * y * x4 * L;

  return psip + c[0] * p1 + c[1] * p2 + c[2] * p3 + c[3] * p4 + c[4] * p5 + c[5] * p6 + c[6] * p7 + c[7] * p8 + c[8] * p9 + c[9] * p10 + c[10] * p11 + c[11] * p12;
}

/* Nonlinear residual F(psi). Linear here, so Newton converges in one step. */
static PetscErrorCode FormFunction(SNES snes, Vec X, Vec F, void *ctx)
{
  AppCtx       *user = (AppCtx *)ctx;
  DM            da;
  Vec           localX;
  PetscInt      i, j, Mx, My, xs, ys, xm, ym;
  PetscReal     hx, hy, x, y;
  PetscScalar **xa, **fa;

  PetscFunctionBeginUser;
  PetscCall(SNESGetDM(snes, &da));
  PetscCall(DMDAGetInfo(da, NULL, &Mx, &My, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL));
  hx = (user->xmax - user->xmin) / (PetscReal)(Mx - 1);
  hy = (user->ymax - user->ymin) / (PetscReal)(My - 1);

  PetscCall(DMGetLocalVector(da, &localX));
  PetscCall(DMGlobalToLocalBegin(da, X, INSERT_VALUES, localX));
  PetscCall(DMGlobalToLocalEnd(da, X, INSERT_VALUES, localX));

  PetscCall(DMDAVecGetArrayRead(da, localX, &xa));
  PetscCall(DMDAVecGetArray(da, F, &fa));
  PetscCall(DMDAGetCorners(da, &xs, &ys, NULL, &xm, &ym, NULL));

  for (j = ys; j < ys + ym; j++) {
    for (i = xs; i < xs + xm; i++) {
      x = user->xmin + i * hx;
      y = user->ymin + j * hy;
      if (i == 0 || j == 0 || i == Mx - 1 || j == My - 1) {
        /* Dirichlet: psi = PsiExact (nonzero on the box edges in general). */
        fa[j][i] = xa[j][i] - PsiExact(user, x, y);
      } else {
        PetscScalar uxx = (xa[j][i + 1] - 2.0 * xa[j][i] + xa[j][i - 1]) / (hx * hx);
        PetscScalar ux  = (xa[j][i + 1] - xa[j][i - 1]) / (2.0 * hx);
        PetscScalar uyy = (xa[j + 1][i] - 2.0 * xa[j][i] + xa[j - 1][i]) / (hy * hy);
        PetscReal   f   = (1.0 - user->A) * x * x + user->A;
        fa[j][i]        = uxx - ux / x + uyy - f;
      }
    }
  }

  PetscCall(DMDAVecRestoreArrayRead(da, localX, &xa));
  PetscCall(DMDAVecRestoreArray(da, F, &fa));
  PetscCall(DMRestoreLocalVector(da, &localX));
  PetscFunctionReturn(PETSC_SUCCESS);
}

/* True Jacobian of the Grad-Shafranov operator. */
static PetscErrorCode FormJacobian(SNES snes, Vec X, Mat J, Mat Jpre, void *ctx)
{
  AppCtx   *user = (AppCtx *)ctx;
  DM        da;
  PetscInt  i, j, Mx, My, xs, ys, xm, ym;
  PetscReal hx, hy, x;

  PetscFunctionBeginUser;
  PetscCall(SNESGetDM(snes, &da));
  PetscCall(DMDAGetInfo(da, NULL, &Mx, &My, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL));
  hx = (user->xmax - user->xmin) / (PetscReal)(Mx - 1);
  hy = (user->ymax - user->ymin) / (PetscReal)(My - 1);

  PetscCall(DMDAGetCorners(da, &xs, &ys, NULL, &xm, &ym, NULL));
  for (j = ys; j < ys + ym; j++) {
    for (i = xs; i < xs + xm; i++) {
      MatStencil  row, col[5];
      PetscScalar v[5];
      PetscInt    n = 0;
      row.i = i;
      row.j = j;
      if (i == 0 || j == 0 || i == Mx - 1 || j == My - 1) {
        col[0].i = i;
        col[0].j = j;
        v[0]     = 1.0;
        n        = 1;
      } else {
        x        = user->xmin + i * hx;
        col[n].i = i;
        col[n].j = j - 1;
        v[n++]   = 1.0 / (hy * hy);
        col[n].i = i - 1;
        col[n].j = j;
        v[n++]   = 1.0 / (hx * hx) + 1.0 / (2.0 * hx * x);
        col[n].i = i;
        col[n].j = j;
        v[n++]   = -2.0 / (hx * hx) - 2.0 / (hy * hy);
        col[n].i = i + 1;
        col[n].j = j;
        v[n++]   = 1.0 / (hx * hx) - 1.0 / (2.0 * hx * x);
        col[n].i = i;
        col[n].j = j + 1;
        v[n++]   = 1.0 / (hy * hy);
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
  SNES                snes;
  DM                  da;
  Vec                 X, F;
  Mat                 J;
  AppCtx              user;
  SNESConvergedReason reason;
  PetscInt            Mx, My, xs, ys, xm, ym, i, j, nc;
  PetscReal           hx, hy, errloc = 0.0, l2loc = 0.0, errinf, l2;
  PetscScalar       **xa;

  PetscFunctionBeginUser;
  PetscCall(PetscInitialize(&argc, &argv, NULL, help));

  /* --- Defaults (ITER case) --- */
  user.xmin = 0.648;
  user.xmax = 1.352;
  user.ymin = -0.5984;
  user.ymax = 0.5984;
  user.A    = -0.155;
  {
    const PetscReal cdef[12] = {0.0666504678, -0.1954979606, -0.0511055413, -0.0459671061, 0.0055324134, -0.0055311112, -0.0001480056, 0.0, 0.0, 0.0, 0.0, 0.0};
    for (i = 0; i < 12; i++) user.c[i] = cdef[i];
  }

  /* --- Options --- */
  PetscCall(PetscOptionsGetReal(NULL, NULL, "-cf_xmin", &user.xmin, NULL));
  PetscCall(PetscOptionsGetReal(NULL, NULL, "-cf_xmax", &user.xmax, NULL));
  PetscCall(PetscOptionsGetReal(NULL, NULL, "-cf_ymin", &user.ymin, NULL));
  PetscCall(PetscOptionsGetReal(NULL, NULL, "-cf_ymax", &user.ymax, NULL));
  PetscCall(PetscOptionsGetReal(NULL, NULL, "-cf_A", &user.A, NULL));
  nc = 12;
  PetscCall(PetscOptionsGetRealArray(NULL, NULL, "-cf_c", user.c, &nc, NULL));

  /* --- DMDA: DM_BOUNDARY_NONE, 1 dof, stencil width 1, 5-point star --- */
  PetscCall(DMDACreate2d(PETSC_COMM_WORLD, DM_BOUNDARY_NONE, DM_BOUNDARY_NONE, DMDA_STENCIL_STAR, 65, 65, PETSC_DECIDE, PETSC_DECIDE, 1, 1, NULL, NULL, &da));
  PetscCall(DMSetFromOptions(da));
  PetscCall(DMSetUp(da));
  PetscCall(DMDASetUniformCoordinates(da, user.xmin, user.xmax, user.ymin, user.ymax, 0.0, 0.0));

  PetscCall(DMDAGetInfo(da, NULL, &Mx, &My, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL));
  hx = (user.xmax - user.xmin) / (PetscReal)(Mx - 1);
  hy = (user.ymax - user.ymin) / (PetscReal)(My - 1);

  /* --- SNES --- */
  PetscCall(SNESCreate(PETSC_COMM_WORLD, &snes));
  PetscCall(SNESSetDM(snes, da));

  PetscCall(DMCreateGlobalVector(da, &X));
  PetscCall(VecDuplicate(X, &F));
  PetscCall(DMCreateMatrix(da, &J));

  PetscCall(SNESSetFunction(snes, F, FormFunction, &user));
  PetscCall(SNESSetJacobian(snes, J, J, FormJacobian, &user));
  PetscCall(SNESSetFromOptions(snes));

  PetscCall(VecSet(X, 0.0));
  PetscCall(SNESSolve(snes, NULL, X));
  PetscCall(SNESGetConvergedReason(snes, &reason));

  /* --- Error against manufactured exact solution --- */
  PetscCall(DMDAVecGetArrayRead(da, X, &xa));
  PetscCall(DMDAGetCorners(da, &xs, &ys, NULL, &xm, &ym, NULL));
  for (j = ys; j < ys + ym; j++) {
    for (i = xs; i < xs + xm; i++) {
      PetscReal x = user.xmin + i * hx;
      PetscReal y = user.ymin + j * hy;
      PetscReal e = PetscAbsScalar(xa[j][i] - PsiExact(&user, x, y));
      if (e > errloc) errloc = e;
      l2loc += e * e;
    }
  }
  PetscCall(DMDAVecRestoreArrayRead(da, X, &xa));

  PetscCallMPI(MPI_Allreduce(&errloc, &errinf, 1, MPIU_REAL, MPIU_MAX, PETSC_COMM_WORLD));
  PetscCallMPI(MPI_Allreduce(&l2loc, &l2, 1, MPIU_REAL, MPIU_SUM, PETSC_COMM_WORLD));
  l2 = PetscSqrtReal(l2 * hx * hy);

  /* --- Report --- */
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Grid            : Nx = %" PetscInt_FMT ", Ny = %" PetscInt_FMT "\n", Mx, My));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Spacing         : hx = %.6e, hy = %.6e\n", (double)hx, (double)hy));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Max-norm error  : ||psi_h - PsiExact||_inf = %.6e\n", (double)errinf));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "Discrete L2 err : %.6e\n", (double)l2));
  PetscCall(PetscPrintf(PETSC_COMM_WORLD, "SNESGetConvergedReason: %s\n", SNESConvergedReasons[reason]));

  PetscCall(VecViewFromOptions(X, NULL, "-psi_view"));

  /* --- Cleanup --- */
  PetscCall(VecDestroy(&X));
  PetscCall(VecDestroy(&F));
  PetscCall(MatDestroy(&J));
  PetscCall(SNESDestroy(&snes));
  PetscCall(DMDestroy(&da));
  PetscCall(PetscFinalize());
  return 0;
}