# Grad–Shafranov Equilibrium — Mathematical Model

**The name of the PDE is [Grad-Shafranov equation]** (the axisymmetric ideal-MHD equilibrium equation).

**the PDE is not time-dependent** (it is a stationary/equilibrium force-balance problem).

A note on the derivation: the Grad–Shafranov operator can be written in the self-adjoint divergence form
$\Delta^*\psi = R^2\,\nabla\!\cdot\!\left(R^{-2}\nabla\psi\right)$. Dividing the strong form by $R^2$, multiplying by a test function $v$ (with $v=0$ on $\partial\Omega$), and integrating by parts yields the symmetric weak form below. Because $p(\psi)$ and $F(\psi)$ depend on $\psi$, the problem is generally nonlinear.

---

### 1) HTML page with MathJax

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Grad-Shafranov Equilibrium</title>
  <script>
    window.MathJax = {
      tex: { inlineMath: [['\\(', '\\)']], displayMath: [['\\[', '\\]']] }
    };
  </script>
  <script id="MathJax-script" async
    src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body>
  <h1>Grad&ndash;Shafranov Equation (axisymmetric ideal-MHD equilibrium)</h1>

  <p>Unknown: poloidal magnetic flux \(\psi(R,Z)\) on the poloidal cross-section
  \(\Omega\subset\{(R,Z):R>0\}\), with \(\mu_0\) the vacuum permeability,
  \(p(\psi)\) the plasma pressure and \(F(\psi)=R\,B_\phi\) the poloidal current
  function. It is a stationary (time-independent) problem.</p>

  <h2>Strong form</h2>
  <p>Grad&ndash;Shafranov operator:</p>
  \[
    \Delta^{*}\psi \;\equiv\;
    R\,\frac{\partial}{\partial R}\!\left(\frac{1}{R}\frac{\partial \psi}{\partial R}\right)
    + \frac{\partial^{2}\psi}{\partial Z^{2}}
    \;=\;
    R^{2}\,\nabla\!\cdot\!\left(\frac{1}{R^{2}}\nabla\psi\right).
  \]
  <p>Equilibrium equation and Dirichlet boundary condition:</p>
  \[
    \Delta^{*}\psi \;=\; -\,\mu_{0}\,R^{2}\,\frac{dp}{d\psi}
                       \;-\; F\,\frac{dF}{d\psi}
    \qquad \text{in } \Omega,
  \]
  \[
    \psi \;=\; \psi_{b} \qquad \text{on } \partial\Omega .
  \]

  <h2>Weak form</h2>
  <p>Find \(\psi\in H^{1}(\Omega)\) with \(\psi=\psi_{b}\) on \(\partial\Omega\)
  such that for all test functions \(v\in H^{1}_{0}(\Omega)\):</p>
  \[
    \int_{\Omega} \frac{1}{R^{2}}\,\nabla\psi\cdot\nabla v \; dR\,dZ
    \;=\;
    \int_{\Omega} \left(\mu_{0}\,\frac{dp}{d\psi}
      + \frac{1}{R^{2}}\,F\,\frac{dF}{d\psi}\right) v \; dR\,dZ ,
  \]
  <p>obtained by dividing the strong form by \(R^{2}\), multiplying by \(v\),
  integrating over \(\Omega\), and integrating by parts (the boundary term
  vanishes since \(v=0\) on \(\partial\Omega\)).</p>
</body>
</html>
```

---

### 2) LaTeX (no document/section wrapper)

```latex
% ---- Grad-Shafranov equilibrium: strong and weak forms ----
% Unknown: poloidal flux psi(R,Z) on poloidal cross-section Omega, R > 0.
% mu0: vacuum permeability, p(psi): pressure, F(psi)=R B_phi: current function.

% Grad-Shafranov (self-adjoint) operator:
\begin{equation*}
  \Delta^{*}\psi \;\equiv\;
  R\,\frac{\partial}{\partial R}\!\left(\frac{1}{R}\frac{\partial \psi}{\partial R}\right)
  + \frac{\partial^{2}\psi}{\partial Z^{2}}
  \;=\; R^{2}\,\nabla\!\cdot\!\left(\frac{1}{R^{2}}\nabla\psi\right).
\end{equation*}

% Strong form + Dirichlet boundary condition:
\begin{align*}
  \Delta^{*}\psi
    &= -\,\mu_{0}\,R^{2}\,\frac{dp}{d\psi}
       \;-\; F\,\frac{dF}{d\psi}
       && \text{in } \Omega, \\
  \psi &= \psi_{b}
       && \text{on } \partial\Omega .
\end{align*}

% Weak form:
% Find psi in H^1(Omega) with psi = psi_b on the boundary such that
% for all v in H^1_0(Omega):
\begin{equation*}
  \int_{\Omega} \frac{1}{R^{2}}\,\nabla\psi\cdot\nabla v \; dR\,dZ
  \;=\;
  \int_{\Omega} \left(\mu_{0}\,\frac{dp}{d\psi}
      + \frac{1}{R^{2}}\,F\,\frac{dF}{d\psi}\right) v \; dR\,dZ .
\end{equation*}
```

---

### 3) UFL (FEniCS)

```python
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
```