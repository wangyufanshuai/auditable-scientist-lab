# Evidence policy

Engineering evidence and scientific evidence are separate dimensions.

| Level | Meaning | Allowed wording |
|---|---|---|
| `demo` | local deterministic example or fixture | “demo” / “algorithm demonstration” |
| `validated-reproduction` | checked against an analytic result or independent backend within declared scope | “validated reproduction within scope” |
| `real-data` | source-tracked public data with provenance and checksums | “real-data demonstration” |
| `research-candidate` | fixed question and scientific gate, not automatically publishable | “research candidate” |

Rules:

- A passing local test does not establish licensing, production readiness, scientific
  validity, novelty, or human acceptance.
- A candidate without a holdout result remains `candidate`.
- Synthetic and fixture data cannot support a `real-data` claim.
- An evidence reference must point to a file, URL, or registered snapshot with a hash and
  provenance status.
- LLM text is explanatory or propositional evidence; it is not the authoritative source
  of numerical results, unit validity, or claim promotion.
- Historical `passed` fields from imported reports are not promoted without current
  replay and scope checks.
- Unknown, blocked, and pending states remain visible in reports.
