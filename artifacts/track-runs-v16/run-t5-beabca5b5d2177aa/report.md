# T5 bounded offline run

- Run: `run-t5-beabca5b5d2177aa`
- Status: `completed`
- Evaluator: `bio-chem-text-protocol-v2`
- Registered tool calls: `1`
- Fixture result: `{"checked_citations":10,"evaluator_id":"bio-chem-text-protocol-v2","evidence_level":"demo","execution_allowed":false,"failures":[],"notes":["The evaluator checks a bounded synthetic text fixture and declared constraints only.","Source rights, real materials, equipment, safety, and human acceptance are unverified.","It never schedules, controls, or authorizes wet-lab execution."],"passed":true,"requires_human_review":true,"review_status":"text-reviewed"}`
- Negative control: `{"checked_citations":10,"evaluator_id":"bio-chem-text-protocol-v2","evidence_level":"demo","execution_allowed":false,"failures":["document-hash:synthetic-buffer-plan-v1","citation-span:step-1:reagent","citation-span:step-1:volume_ul","citation-span:step-1:temperature_c","citation-span:step-1:duration_min","citation-step:step-1:duration_min","citation-span:step-2:action","citation-span:step-2:reagent","citation-span:step-2:volume_ul","citation-span:step-2:temperature_c","citation-span:step-2:duration_min","citation-step:step-2:duration_min"],"notes":["The evaluator checks a bounded synthetic text fixture and declared constraints only.","Source rights, real materials, equipment, safety, and human acceptance are unverified.","It never schedules, controls, or authorizes wet-lab execution."],"passed":false,"requires_human_review":true,"review_status":"blocked"}`
- Claim status: `unverified`
- Real-data, research-candidate, and publication claims: `false`

This run checks a local fixture only. T5 never authorizes wet-lab execution.
