
# Grad-Shafranov equilibrium (axisymmetric ideal-MHD), weak form in UFL/FEniCS.
# Name: Grad-Shafranov equation. It is NOT time-dependent (equilibrium problem).
#
# Strong form:   Delta*_psi = -mu0 * R^2 * dp/dpsi - F * dF/dpsi ,  psi = psi_b on boundary
# with Delta*_psi = R^2 * div( (1/R^2) grad(psi) ).
# Dividing by R^2 and multiplying by a test function v (v = 0 on boundary),
# then integrating by parts gives the weak/residual form below.

from fenics import (FunctionSpace, Function, TestFunction, DirichletBC,
                    SpatialCoordinate, Constant, solve)
from ufl import dot, grad, dx, pi

# --- Mesh: poloidal (R,Z) cross-section Omega (supplied elsewhere) ---
# mesh = ...
V = FunctionSpace(mesh, "CG", 1)

# Radial coordinate R = x[0], vertical coordinate Z = x[1]
x = SpatialCoordinate(mesh)
R = x[0]

# Physical constant (vacuum permeability)
mu0 = Constant(4.0e-7) * pi

# Unknown poloidal flux and test function
psi = Function(V)          # psi(R,Z)
v   = TestFunction(V)       # v in H^1_0(Omega)

# Free-function profiles as UFL expressions in psi:
#   dpdpsi = dp/dpsi ,   FdFdpsi = F * dF/dpsi
# (Replace with the desired closures; they generally depend on psi.)
dpdpsi  = Constant(0.0)     # e.g. some function of psi
FdFdpsi = Constant(0.0)     # e.g. some function of psi

# Dirichlet boundary condition: psi = psi_b on the boundary
psi_b = Constant(0.0)
bc = DirichletBC(V, psi_b, "on_boundary")

# Weak (residual) form:
#   ∫ (1/R^2) grad(psi)·grad(v) dRdZ
#     - ∫ ( mu0 * dp/dpsi + (1/R^2) * F dF/dpsi ) v dRdZ = 0
Res = ( (1.0 / R**2) * dot(grad(psi), grad(v)) ) * dx \
      - ( mu0 * dpdpsi + (1.0 / R**2) * FdFdpsi ) * v * dx

# Solve the (generally nonlinear) equilibrium problem
solve(Res == 0, psi, bc)
