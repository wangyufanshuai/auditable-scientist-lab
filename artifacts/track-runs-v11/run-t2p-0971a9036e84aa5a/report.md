# T2P bounded offline run

- Run: `run-t2p-0971a9036e84aa5a`
- Status: `completed`
- Evaluator: `planar-ball-counterfactual-v1`
- Registered tool calls: `1`
- Fixture result: `{"case_count":100,"direction_passed":true,"evaluator_id":"planar-ball-counterfactual-v1","holdout_count":60,"ignored_intervention_holdout_rmse":0.24218293514086056,"ignored_intervention_rejected":true,"max_first_impact_time_error":0.0,"max_first_rebound_apex_error":0.0,"max_free_flight_energy_residual":7.105427357601002e-15,"max_impact_energy_gain":0.0,"max_noop_trajectory_delta":0.0,"notes":["Exactly specified two-dimensional ballistic flight with floor collisions; horizontal friction acts only at impact.","Factual and counterfactual share the same initial state; do(parameter=value) replaces a parameter, not an observational association.","Deterministic simulator uncertainty is zero only within its equations; real-world model discrepancy is not quantified."],"passed":true,"query_counts":{"joint":20,"policy":20,"single":60},"simulator_id":"analytic-flight-event-collision-v1","train_count":40}`
- Negative control: `{"estimator":"ignores-intervention","holdout_rmse":0.24218293514086056,"rejected":true}`
- Claim status: `unverified`
- Real-data, research-candidate, and publication claims: `false`

This run checks a local fixture only. T5 never authorizes wet-lab execution.
