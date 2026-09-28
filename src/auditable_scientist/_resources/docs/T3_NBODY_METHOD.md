# T3 symmetric three-body benchmark

This local, dimensionless fixture exercises a narrow planar Newtonian three-body solution. It does not validate perturbed or nonintegrable motion, real celestial ephemerides, mission design, or a general N-body solver. The original paper by [Chenciner and Montgomery](https://arxiv.org/pdf/math/0011268) describes the equilateral relative equilibrium; the implementation below derives its own expected state and copies no external data or code. The [NASA NTRS record](https://ntrs.nasa.gov/citations/19730059032) independently documents equilateral solutions in the three-body literature.

For positive masses $m_i$, common side $a$, barycentric positions $q_i$ and $M=\sum_i m_i$, the Newtonian acceleration is

$$\ddot q_i=\frac{G}{a^3}\sum_{j\ne i}m_j(q_j-q_i)=-\frac{GM}{a^3}q_i.$$

Thus $\omega=\sqrt{GM/a^3}$ and $q_i(t)=R(\omega t)q_i(0)$ when $\dot q_i(0)=\omega(-q_{iy},q_{ix})$. This identity holds for an equilateral configuration with the declared positive masses. The code uses velocity-Verlet, an independently written Cartesian RK4, and the analytic rotation. It measures position discrepancy relative to $a$, total-energy and angular-momentum drift relative to their nonzero initial values, barycenter drift relative to $a$, and pairwise separation drift relative to $a$.

Predeclared gates: Verlet analytic error ≤ 0.001, RK4 analytic error ≤ 0.00001, inter-backend position delta ≤ 0.001, relative energy drift ≤ 0.0001, relative angular-momentum drift ≤ 1e-10, barycenter drift ≤ 1e-10, and pair-distance error ≤ 0.001. A repulsive-force negative control on the holdout initial condition must differ from the attractive analytic orbit by more than 0.1 side lengths. Both train and holdout cases must pass. Parameters are bounded to positive finite dimensionless values, at most one orbit and at most 10,000 steps. All Run claims remain unverified, and fixture provenance remains unverified.
