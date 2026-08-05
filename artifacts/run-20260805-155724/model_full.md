## Mathematical Model — Grad–Shafranov (Solov'ev / Cerfon–Freidberg)

Statement: **the PDE is not time-dependent**

**The name of the PDE is [Grad-Shafranov equation]**

Below, `x = R/R0`, `y = Z/R0`, `A` is the Solov'ev constant (encoding the ratio of pressure to poloidal-current forcing), and the Cerfon–Freidberg-normalized source is `S(x) = (1-A)x^2 + A`. The elongation, triangularity and inverse aspect ratio enter through the shape of the domain `Ω` (D-shaped, possibly with an X-point) and the homogeneous Dirichlet condition on `∂Ω`.

---

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Grad–Shafranov Equilibrium (Solov'ev / Cerfon–Freidberg)</title>
<script>
  window.MathJax = {
    tex: { inlineMath: [['\\(','\\)']], displayMath: [['$$','$$'],['\\[','\\]']] }
  };
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
</head>
<body>
<h1>Grad&ndash;Shafranov Equilibrium (Solov'ev / Cerfon&ndash;Freidberg)</h1>

<h2>Dimensional strong form</h2>
<p>The axisymmetric ideal-MHD force balance for the poloidal flux \(\psi(R,Z)\):</p>
$$
\Delta^{*}\psi
\;\equiv\; R\,\frac{\partial}{\partial R}\!\left(\frac{1}{R}\frac{\partial \psi}{\partial R}\right)
+ \frac{\partial^{2}\psi}{\partial Z^{2}}
\;=\; -\,\mu_{0}R^{2}\,\frac{dp}{d\psi} \;-\; F\,\frac{dF}{d\psi}.
$$

<h2>Normalized (Solov'ev) strong form</h2>
<p>With \(x=R/R_{0}\), \(y=Z/R_{0}\), and Solov'ev profiles
(\(dp/d\psi,\;F\,dF/d\psi\) constant), the source collapses to \((1-A)x^{2}+A\):</p>
$$
\Delta^{*}\psi
\;\equiv\;\frac{\partial^{2}\psi}{\partial x^{2}}
-\frac{1}{x}\frac{\partial \psi}{\partial x}
+\frac{\partial^{2}\psi}{\partial y^{2}}
\;=\;x\,\nabla\!\cdot\!\Big(\tfrac{1}{x}\,\nabla\psi\Big)
\;=\;(1-A)\,x^{2}+A
\quad\text{in }\Omega,
$$
$$
\psi = 0 \quad\text{on }\partial\Omega,
$$
<p>where \(\Omega\) is the poloidal cross-section whose boundary \(\partial\Omega\)
carries the prescribed D-shape (inverse aspect ratio \(\epsilon\), elongation \(\kappa\),
triangularity \(\delta\), optional X-point).</p>

<h2>Weak (variational) form</h2>
<p>Multiply \(\Delta^{*}\psi = S\) with \(S(x)=(1-A)x^{2}+A\) by a test function
\(v\in H_{0}^{1}(\Omega)\), divide by \(x\), and integrate by parts (using
\(\Delta^{*}\psi = x\,\nabla\!\cdot(\tfrac1x\nabla\psi)\)). The boundary term
vanishes since \(v|_{\partial\Omega}=0\). Find \(\psi\in H^{1}(\Omega)\) with
\(\psi=0\) on \(\partial\Omega\) such that</p>
$$
\int_{\Omega}\frac{1}{x}\,\nabla\psi\cdot\nabla v \;\, dx\,dy
\;=\;
-\int_{\Omega}\frac{(1-A)x^{2}+A}{x}\,v \;\, dx\,dy
\qquad \forall\, v\in H_{0}^{1}(\Omega).
$$
</body>
</html>
```

```latex
% Grad--Shafranov equilibrium, Solov'ev profiles (Cerfon--Freidberg normalization)
% x = R/R0, y = Z/R0, A = Solov'ev constant, S(x) = (1-A)x^2 + A.

% ---------- Dimensional strong form ----------
\[
\Delta^{*}\psi
\;\equiv\; R\,\frac{\partial}{\partial R}\!\left(\frac{1}{R}\frac{\partial \psi}{\partial R}\right)
+ \frac{\partial^{2}\psi}{\partial Z^{2}}
\;=\; -\,\mu_{0}R^{2}\,\frac{dp}{d\psi} \;-\; F\,\frac{dF}{d\psi}.
\]

% ---------- Normalized (Solov'ev) strong form ----------
\[
\Delta^{*}\psi
\;\equiv\;\frac{\partial^{2}\psi}{\partial x^{2}}
-\frac{1}{x}\frac{\partial \psi}{\partial x}
+\frac{\partial^{2}\psi}{\partial y^{2}}
\;=\; x\,\nabla\!\cdot\!\Big(\tfrac{1}{x}\,\nabla\psi\Big)
\;=\;(1-A)\,x^{2}+A
\quad \text{in } \Omega,
\]
\[
\psi = 0 \quad \text{on } \partial\Omega .
\]

% ---------- Weak (variational) form ----------
% Find psi in H^1(Omega), psi = 0 on dOmega, such that for all v in H^1_0(Omega):
\[
\int_{\Omega}\frac{1}{x}\,\nabla\psi\cdot\nabla v \;\, dx\,dy
\;=\;
-\int_{\Omega}\frac{(1-A)x^{2}+A}{x}\,v \;\, dx\,dy
\qquad \forall\, v \in H_{0}^{1}(\Omega).
\]
```

```python
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
```