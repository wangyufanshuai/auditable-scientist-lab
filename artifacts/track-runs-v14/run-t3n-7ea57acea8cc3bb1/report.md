# T3N bounded offline run

- Run: `run-t3n-7ea57acea8cc3bb1`
- Status: `completed`
- Evaluator: `equilateral-three-body-v1`
- Registered tool calls: `1`
- Fixture result: `{"case_results":[{"backend_position_delta":4.5919667316087405e-06,"case_id":"equal-train","center_of_mass_drift":2.0833328401076663e-15,"pair_distance_error":3.4269401045783354e-06,"relative_angular_momentum_drift":1.2819751242557094e-15,"relative_energy_drift":1.1742902946328586e-11,"rk4_position_error":2.13842996948953e-12,"split":"train","verlet_position_error":4.591964595699146e-06},{"backend_position_delta":9.586923065942161e-06,"case_id":"unequal-holdout","center_of_mass_drift":2.3524239568466423e-15,"pair_distance_error":3.4269401019138e-06,"relative_angular_momentum_drift":1.3557840954560823e-15,"relative_energy_drift":1.1744876676150144e-11,"rk4_position_error":4.462785156203479e-12,"split":"holdout","verlet_position_error":9.58691860323117e-06}],"evaluator_id":"equilateral-three-body-v1","max_backend_position_delta":9.586923065942161e-06,"max_center_of_mass_drift":2.3524239568466423e-15,"max_pair_distance_error":3.4269401045783354e-06,"max_relative_angular_momentum_drift":1.3557840954560823e-15,"max_relative_energy_drift":1.1744876676150144e-11,"max_rk4_position_error":4.462785156203479e-12,"max_verlet_position_error":9.58691860323117e-06,"negative_force_rejected":true,"negative_repulsive_force_error":5.597864749772271,"notes":["Dimensionless, equilateral circular initial conditions only; the orbit has a direct analytic reference.","Velocity-Verlet and a separately coded Cartesian RK4 are compared to that reference.","No perturbed three-body, real mission, or general N-body validity is inferred."],"passed":true,"reference_solver_id":"independent-cartesian-rk4-v1","solver_id":"velocity-verlet-pairwise-v1"}`
- Negative control: `{"force":"repulsive","position_error":5.597864749772271,"rejected":true}`
- Claim status: `unverified`
- Real-data, research-candidate, and publication claims: `false`

This run checks a local fixture only. T5 never authorizes wet-lab execution.
