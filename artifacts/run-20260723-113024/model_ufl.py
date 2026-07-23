
# Grad-Shafranov equilibrium in UFL (FEniCS / FEniCSx).
# Stationary (time-independent), nonlinear residual form.
#
# Strong form:   Delta* psi = -mu0 R^2 dp/dpsi - F dF/dpsi  in Omega
#                psi = psi_b                                 on boundary
# with Delta* psi = R^2 div( (1/R^2) grad psi ).
#
# Dividing by R^2 and integrating by parts (v = 0 on the Dirichlet
# boundary) gives the symmetric weak form implemented below.

from ufl import (Coefficient, TestFunction, TrialFunction,
                 SpatialCoordinate, grad, dot, dx, Constant)

# --- Assume a 2D poloidal (R,Z) mesh and a scalar space V are defined ---
# mesh = ...            # 2D mesh of the poloidal cross-section Omega
# V    = ...            # e.g. FunctionSpace(mesh, "Lagrange", 1)

psi = Coefficient(V)     # unknown poloidal flux psi(R,Z)  (nonlinear solve)
v   = TestFunction(V)    # test function, v = 0 on Dirichlet boundary
dpsi = TrialFunction(V)  # increment for the Jacobian (Newton)

x = SpatialCoordinate(mesh)
R = x[0]                 # major-radius coordinate  (R > 0)
# Z = x[1]               # vertical coordinate

mu0 = Constant(mesh)     # vacuum permeability  (assign 4*pi*1e-7)

# Profile source terms; these are functions of psi (make the problem
# nonlinear). Replace by the chosen equilibrium profiles p(psi), F(psi):
#   p_prime  = dp/dpsi    evaluated at psi
#   FFprime  = F dF/dpsi  evaluated at psi
p_prime = Coefficient(V)   # placeholder for dp/dpsi(psi)
FFprime = Coefficient(V)   # placeholder for F dF/dpsi(psi)

# Weak (residual) form  R(psi; v) = 0:
#   find psi with psi = psi_b on the boundary such that for all v:
F_res = ( (1.0 / R**2) * dot(grad(psi), grad(v)) * dx
          - ( mu0 * p_prime + (1.0 / R**2) * FFprime ) * v * dx )

# Jacobian (Gateaux derivative) for a Newton solver:
from ufl import derivative
J = derivative(F_res, psi, dpsi)

# The Dirichlet condition psi = psi_b on partial-Omega is imposed as an
# essential BC on V when assembling/solving (not part of the UFL form).
