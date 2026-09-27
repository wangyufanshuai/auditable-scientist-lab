# T3 figure-eight numerical protocol

The [source paper](https://perso.imcce.fr/alain-chenciner/huit.pdf) by
Chenciner and Montgomery (Annals of Mathematics 152, 2000,
[DOI 10.2307/2661357](https://doi.org/10.2307/2661357)) prints Carles Simó's
approximate equal-mass figure-eight initial state and period in Figure 1.
The downloaded PDF has SHA-256
`f470bde538ded751695434f3d67c79fb8257beca58529ae8bf01e0fb2191b16f`;
the PDF is not redistributed. These published decimal values are transcribed
into the [machine-readable protocol](T3_FIGURE_EIGHT_PROTOCOL.json).

This protocol freezes a one-period published-state check, a ten-period check,
and a ten-period momentum-balanced velocity perturbation. It fixes DOP853 and
independently coded Cartesian RK4 settings, pair-separation event rejection,
conservation diagnostics, a wrong-sign force negative control, and a bounded
compute budget before evaluating endpoints. The one-period closure is checked
against the approximate published state. Ten-period closure is reported but
is not a gate because the paper provides only rounded decimal initial values.

The figure-eight is one special Newtonian three-body trajectory. Agreement
between numerical solvers under this finite protocol would show bounded
reproduction of that published problem, not chaotic-regime accuracy, general
N-body correctness, real ephemeris comparison, scientific holdout, or mission
validation. Those gates remain open; the scientific Claim stays `unverified`.
