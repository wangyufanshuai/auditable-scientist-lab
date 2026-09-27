# Optional T3 SciPy cross-check

The core package and its five replay receipts do not depend on SciPy. This
separate audit installs SciPy 1.18.1 and NumPy 2.2.6 in an isolated Windows
AMD64 / CPython 3.12.3 environment, then compares SciPy's adaptive `DOP853`
solver with the analytic unit-mass harmonic oscillator, local Velocity-Verlet,
and local fixed-step RK4 implementations. It records nine frequency/initial
state cases and a wrong-sign acceleration negative control.

The API and method were checked against the official
[SciPy `solve_ivp` reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).
The audited SciPy source tag is
[`v1.18.1`](https://github.com/scipy/scipy/tree/v1.18.1) at commit
`c2df8ace0d9859f090e79058b2bd2ffc584f19e6`;
the NumPy source tag is
[`v2.2.6`](https://github.com/numpy/numpy/tree/v2.2.6) at commit
`bbb76e7d76c3748fb2747fc3d8e06b944005362a`.
Their [SciPy license](https://github.com/scipy/scipy/blob/v1.18.1/LICENSE.txt),
[SciPy bundled-license inventory](https://github.com/scipy/scipy/blob/v1.18.1/LICENSES_bundled.txt),
and [NumPy license](https://github.com/numpy/numpy/blob/v2.2.6/LICENSE.txt)
were read. Both projects use BSD-style terms requiring preservation of notices
on redistribution; the binary wheels include additional license notices.
This repository does not vendor or redistribute either wheel.

The optional requirements file pins the exact Windows wheels by SHA-256:
`scipy-1.18.1-cp312-cp312-win_amd64.whl` is
`5e4d44984abc0020154ea81b247adeddcc3ac5527b975ff798bd1ba0adc513c2`;
`numpy-2.2.6-cp312-cp312-win_amd64.whl` is
`c1f9540be57940698ed329904db803cf7a402f3fc200bfe599334c9bd84a40b2`.
The audit also checks the installed license-file hashes. The hashes identify
these wheel bytes, not every possible build of these versions.

To verify the committed [external solver audit](../artifacts/t3-external-scipy.json)
from the repository root, use a new virtual environment:

```powershell
$solverVenv = Join-Path $env:TEMP ("auditable-scientist-scipy-" + [guid]::NewGuid().ToString("N"))
python -m venv $solverVenv
$solverPython = Join-Path $solverVenv "Scripts\python.exe"
& $solverPython -m pip install -e . -c requirements-replay-win-py312.txt
& $solverPython -m pip install -r requirements-t3-scipy-win-py312.txt
& $solverPython -m pip check
& $solverPython scripts/verify_t3_external_scipy.py --verify
```

The nine cases passed solver success, analytic position/velocity accuracy,
normalized energy drift, agreement with both local solvers, and rejection of
the wrong-sign negative control. The maximum normalized SciPy position error
was `1.883e-11`; its maximum energy drift was `3.919e-11`. These measurements
apply only to the declared linear oscillator grid and tolerance settings.
They do not validate multi-body mechanics, real mission trajectories, long-run
stability, or scientific publication. Incorporating an external solver into a
tracked Run would require its own versioned Tool/Provider contract, wheel and
license provenance, resource budget, and replay evidence.
