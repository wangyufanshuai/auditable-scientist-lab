# T3 bounded offline run

- Run: `run-t3-1c4eb6b867515637`
- Status: `completed`
- Evaluator: `harmonic-dynamics-v2`
- Registered tool calls: `1`
- Fixture result: `{"backend_agreement_passed":true,"evaluator_id":"harmonic-dynamics-v2","holdout_max_position_error":1.0495796261222878e-05,"max_backend_position_delta":1.9978152767885504e-05,"max_energy_drift":1.2499992203318655e-05,"max_reference_energy_drift":1.3855472325019491e-11,"max_reference_position_error":4.824394772562357e-10,"negative_euler_rejected":true,"notes":["Velocity-Verlet and independently implemented fixed-step RK4 are compared with the closed-form harmonic solution.","Explicit Euler is a required negative control for conservation drift.","The RK4 method citation is a reference, not an imported software or data dependency."],"passed":true,"reference_solver_id":"fixed-step-rk4-v1","solver_id":"velocity-verlet-v1","train_max_position_error":1.9977752245103897e-05}`
- Negative control: `{"rejected":true,"solver":"explicit-euler"}`
- Claim status: `unverified`
- Real-data, research-candidate, and publication claims: `false`

This run checks a local fixture only. T5 never authorizes wet-lab execution.
