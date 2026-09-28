# T2 bounded offline run

- Run: `run-t2-e8c0533775f1ab69`
- Status: `completed`
- Evaluator: `causal-intervention-v1`
- Registered tool calls: `1`
- Fixture result: `{"coefficient":2.0,"evaluator_id":"causal-intervention-v1","holdout_rmse":0.0,"intercept":1.0,"max_context_invariance_error":0.0,"negative_candidate_rejected":true,"notes":["Intervention outcome uses do(x=value); context_value is intentionally ignored.","Negative candidate is required to fail the holdout gate."],"passed":true,"train_rmse":0.0}`
- Negative control: `{"rejected":true,"wrong_coefficient":1.0}`
- Claim status: `unverified`
- Real-data, research-candidate, and publication claims: `false`

This run checks a local fixture only. T5 never authorizes wet-lab execution.
