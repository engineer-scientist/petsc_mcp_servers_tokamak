## Grad–Shafranov Equilibrium — Mathematical Model

**The name of the PDE is [Grad-Shafranov equation]** (the axisymmetric ideal-MHD equilibrium equation).

**the PDE is not time-dependent** (it is an equilibrium / force-balance equation).

Below, the Grad–Shafranov operator is written both explicitly and in divergence form,
$$\Delta^\* \psi \;=\; R\,\partial_R\!\Big(\tfrac{1}{R}\,\partial_R\psi\Big)+\partial_{ZZ}\psi \;=\; R^2\,\nabla\!\cdot\!\Big(\tfrac{1}{R^2}\nabla\psi\Big),$$
and the weak form is obtained after dividing by $R^2$ (self-adjoint form), multiplying by $v\in H^1_0(\Omega)$, and integrating by parts (the boundary term vanishes because $v=0$ on $\partial\Omega$).

---

### 1) HTML + MathJax

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Grad-Shafranov Equation: Strong and Weak Form</title>
  <script>
    window.MathJax = {
      tex: { inlineMath: [['\\(', '\\)']], displayMath: [['$$', '$$'], ['\\[', '\\]']] }
    };
  </script>
  <script async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body>
  <h1>Grad&ndash;Shafranov Equilibrium (axisymmetric ideal MHD)</h1>

  <p><strong>Name:</strong> Grad&ndash;Shafranov equation. It is an equilibrium PDE, i.e.
  it is <em>not</em> time-dependent.</p>

  <h2>Grad&ndash;Shafranov operator</h2>
  <p>
  \[
    \Delta^{*}\psi \;=\; R\,\frac{\partial}{\partial R}\!\left(\frac{1}{R}\frac{\partial \psi}{\partial R}\right)
    + \frac{\partial^{2}\psi}{\partial Z^{2}}
    \;=\; R^{2}\,\nabla\!\cdot\!\left(\frac{1}{R^{2}}\nabla\psi\right).
  \]
  </p>

  <h2>Strong form</h2>
  <p>Find \(\psi(R,Z)\) on the poloidal cross-section \(\Omega\) such that
  \[
    \Delta^{*}\psi
    \;=\; -\,\mu_{0}\,R^{2}\,\frac{dp}{d\psi}\;-\;F\,\frac{dF}{d\psi}
    \qquad \text{in } \Omega,
  \]
  \[
    \psi = \psi_{b} \qquad \text{on } \partial\Omega \quad(\text{Dirichlet}).
  \]
  Equivalently, dividing by \(R^{2}\),
  \[
    -\,\nabla\!\cdot\!\left(\frac{1}{R^{2}}\nabla\psi\right)
    \;=\; \mu_{0}\,\frac{dp}{d\psi}\;+\;\frac{1}{R^{2}}\,F\,\frac{dF}{d\psi}
    \qquad \text{in } \Omega.
  \]
  </p>

  <h2>Weak form</h2>
  <p>Find \(\psi\in H^{1}(\Omega)\) with \(\psi=\psi_{b}\) on \(\partial\Omega\) such that
  for all test functions \(v\in H^{1}_{0}(\Omega)\),
  \[
    \int_{\Omega} \frac{1}{R^{2}}\,\nabla\psi\cdot\nabla v \; dR\,dZ
    \;=\;
    \int_{\Omega}\!\left(\mu_{0}\,\frac{dp}{d\psi}
    + \frac{1}{R^{2}}\,F\,\frac{dF}{d\psi}\right) v \; dR\,dZ .
  \]
  </p>
</body>
</html>
```

---

### 2) LaTeX

```latex
% Grad-Shafranov equation: strong and weak form
% Name: Grad-Shafranov equation. Not time-dependent (equilibrium).

% Grad-Shafranov operator:
\begin{equation}
  \Delta^{*}\psi
  = R\,\frac{\partial}{\partial R}\!\left(\frac{1}{R}\frac{\partial \psi}{\partial R}\right)
  + \frac{\partial^{2}\psi}{\partial Z^{2}}
  = R^{2}\,\nabla\!\cdot\!\left(\frac{1}{R^{2}}\nabla\psi\right).
\end{equation}

% Strong form:
\begin{align}
  \Delta^{*}\psi
  &= -\,\mu_{0}\,R^{2}\,\frac{dp}{d\psi} - F\,\frac{dF}{d\psi}
  && \text{in } \Omega, \\
  \psi &= \psi_{b}
  && \text{on } \partial\Omega \quad (\text{Dirichlet}).
\end{align}

% Equivalent divergence (self-adjoint) form, after dividing by R^2:
\begin{equation}
  -\,\nabla\!\cdot\!\left(\frac{1}{R^{2}}\nabla\psi\right)
  = \mu_{0}\,\frac{dp}{d\psi} + \frac{1}{R^{2}}\,F\,\frac{dF}{d\psi}
  \qquad \text{in } \Omega.
\end{equation}

% Weak form: find psi in H^1(Omega) with psi = psi_b on the boundary,
% such that for all v in H^1_0(Omega):
\begin{equation}
  \int_{\Omega} \frac{1}{R^{2}}\,\nabla\psi\cdot\nabla v \,\, dR\,dZ
  = \int_{\Omega}\!\left(\mu_{0}\,\frac{dp}{d\psi}
  + \frac{1}{R^{2}}\,F\,\frac{dF}{d\psi}\right) v \,\, dR\,dZ .
\end{equation}
```

---

### 3) UFL (FEniCS)

```python
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
```