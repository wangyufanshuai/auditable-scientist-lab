# T5 bounded offline run

- Run: `run-t5-cc6170f111df81a8`
- Status: `completed`
- Evaluator: `bio-chem-protocol-v1`
- Registered tool calls: `1`
- Fixture result: `{"evaluator_id":"bio-chem-protocol-v1","evidence_level":"validated-reproduction","execution_allowed":false,"failures":[],"notes":["This evaluator checks declarative constraints only.","It never schedules, controls, or authorizes wet-lab execution."],"passed":true}`
- Negative control: `{"evaluator_id":"bio-chem-protocol-v1","evidence_level":"demo","execution_allowed":false,"failures":["provenance:step-1"],"notes":["This evaluator checks declarative constraints only.","It never schedules, controls, or authorizes wet-lab execution."],"passed":false}`
- Claim status: `unverified`
- Real-data, research-candidate, and publication claims: `false`

This run checks a local fixture only. T5 never authorizes wet-lab execution.
