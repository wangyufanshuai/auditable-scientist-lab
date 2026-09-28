# Exact velocity-Verlet discrete invariant

This optional T4 receipt proves one algebraic property of the declared
velocity-Verlet update for a harmonic oscillator. With
$q=(\omega\Delta t)^2$, the update matrix is

$$
A=\begin{pmatrix}1-q/2&\Delta t\\
-\omega^2\Delta t(1-q/4)&1-q/2\end{pmatrix}.
$$

For $0<q<4$, the positive diagonal matrix
$K=\operatorname{diag}(\omega^2(1-q/4),1)$ satisfies
$A^TKA=K$. The quadratic quantity
$\omega^2(1-q/4)x^2+v^2$ is therefore an exact invariant of this
*discrete rational map*. The protocol uses $\omega=3/2$ and
$\Delta t=1/10$, computes every coefficient with `Fraction`, and rejects an
explicit-Euler matrix as a negative control because its residual is nonzero.

The certificate binds the current T3 solver source by SHA-256, but it does not
prove that binary floating-point execution follows exact rational arithmetic,
that a physical oscillator has this model, or that nonlinear or real systems
obey it. Those gates remain open. The receipt is [t4-verlet-invariant-audit.json](../artifacts/t4-verlet-invariant-audit.json).
