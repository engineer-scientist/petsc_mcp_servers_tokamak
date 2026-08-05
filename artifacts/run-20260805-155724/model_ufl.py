
# Grad--Shafranov equilibrium with Solov'ev profiles (Cerfon--Freidberg normalization)
# Strong form:  Delta* psi = x * div( (1/x) grad psi ) = (1-A) x^2 + A  in Omega,  psi = 0 on dOmega
# Weak form:    (1/x) grad(psi) . grad(v) dx  =  -((1-A)x^2 + A)/x * v dx,   v in H^1_0(Omega)

from dolfin import (Mesh, FunctionSpace, TrialFunction, TestFunction, Function,
                    DirichletBC, Constant, SpatialCoordinate, dot, grad, dx, solve)

# --- Solov'ev constant (set from p'(psi) / F F'(psi) ratio for the target machine) ---
A = Constant(-0.155)          # example value

# --- Poloidal cross-section Omega (D-shaped boundary: epsilon, kappa, delta, X-point) ---
mesh = Mesh("tokamak_poloidal.xml")
V = FunctionSpace(mesh, "Lagrange", 2)

# Normalized coordinates x = R/R0, y = Z/R0
X = SpatialCoordinate(mesh)
x = X[0]
y = X[1]

# Homogeneous Dirichlet BC on the poloidal box / plasma boundary
bc = DirichletBC(V, Constant(0.0), "on_boundary")

# Trial / test functions
psi = TrialFunction(V)
v   = TestFunction(V)

# Cerfon--Freidberg normalized Solov'ev source term
S = (1 - A) * x**2 + A

# Bilinear and linear forms (the 1/x weight comes from Delta* = x div( (1/x) grad ))
a = (1.0 / x) * dot(grad(psi), grad(v)) * dx
L = -(S / x) * v * dx

# Solve the (time-independent) equilibrium problem
psi_h = Function(V)
solve(a == L, psi_h, bc)
