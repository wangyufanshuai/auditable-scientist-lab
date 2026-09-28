# T1 MAVEN desaturation sensitivity protocol

This [machine-readable protocol](T1_MAVEN_DESAT_SENSITIVITY_PROTOCOL.json)
freezes a conditional impulse experiment before computing its endpoints. The
author-hosted [MAVEN Navigation Overview](https://drewryanjones.com/assets/conf_paper_2016_no1.pdf)
(Jesick et al., AAS 16-237, 2016) reports approximately weekly cruise
attitude-control desaturations and an estimated **average** translational
impulse of `0.47 mm/s` (PDF page 2). It also says TCM-2 on 2014-02-26 was the
last executed trajectory correction before Mars orbit insertion (page 10).
The latter statement does not exclude later desaturations. The paper's
navigation solution estimated solar-radiation-pressure effects, which the
current local force model does not include. Its PDF is fingerprinted locally;
distribution rights are unresolved, so it is excluded from Git.

The experiment keeps the two previously inspected 24-hour NAV arcs and the
predeclared Sun-plus-planetary-tides force model. It inserts a hypothetical
instantaneous `0.47 mm/s` velocity change at the start or midpoint of each
arc, in each positive and negative radial, transverse, and orbit-normal
direction, for 24 scenario evaluations total. The directions are defined
from the no-impulse state at the insertion time. Each scenario is integrated
at 600 and 300 second steps, with split-run and opposite-sign controls, and
all endpoint response vectors are reported. The JSON fixes numerical gates
and query/step budgets.

This is a response-scale calculation. The publication gives an average
impulse, not a maximum, confidence interval, event time, event direction, or
evidence that either frozen arc contained a desaturation. No scenario is fit
to the NAV endpoint. Even a passing calculation cannot establish actual
mission uncertainty or independent validation of the archived NAV solution.
The scientific Claim remains `unverified`.
