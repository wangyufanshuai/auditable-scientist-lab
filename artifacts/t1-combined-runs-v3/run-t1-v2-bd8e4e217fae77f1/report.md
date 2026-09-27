# Auditable Scientist Lab — T1 combined Run v2

- Run: `run-t1-v2-bd8e4e217fae77f1`; status: `completed`
- Selected candidate: `tof-semimajor-pi-v2`
- Fixed holdout RMSE: `2.6152091439906184e-13` days; threshold: `1e-08` days
- Numerical backend: `internal-rk4-t1-orbit-v2`; cases: `9`
- Maximum relative TOF error: `3.7910732395937486e-12`
- Maximum relative position error: `4.814766465185319e-11`
- Numerical gates: `{'all_apoapses_detected': True, 'all_errors_bounded': True, 'time_error_shrinks_on_refinement': True, 'repulsive_force_rejected': True, 'bounded_compute': True}`
- Synthetic-fixture Claim: `reproduced` at `validated-reproduction`
- Mission Claim: `unverified` at `demo`
- Replay: `pending`

The departure state uses analytic vis-viva. This checks only bounded time propagation within synthetic circular two-body assumptions. Dated ephemerides, source rights, mission geometry, novelty, and publication review remain open.
