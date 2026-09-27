# T3 bounded offline run

- Run: `run-t3-1c4eb6b867515637`
- Status: `completed`
- Evaluator: `harmonic-dynamics-v1`
- Registered tool calls: `1`
- Fixture result: `{"evaluator_id":"harmonic-dynamics-v1","holdout_max_position_error":1.0495796261222878e-05,"max_energy_drift":1.2499992203318655e-05,"negative_euler_rejected":true,"notes":["Velocity-Verlet is compared with the closed-form harmonic solution.","Explicit Euler is a required negative control for conservation drift."],"passed":true,"solver_id":"velocity-verlet-v1","train_max_position_error":1.9977752245103897e-05}`
- Negative control: `{"rejected":true,"solver":"explicit-euler"}`
- Claim status: `unverified`
- Real-data, research-candidate, and publication claims: `false`

This run checks a local fixture only. T5 never authorizes wet-lab execution.
